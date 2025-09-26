import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from lncrawl.core.sources import SourceManager
from lncrawl.binders.epub import EbookBuilder
from lncrawl.database import Database

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        if not self.TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable not set.")
        
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable not set.")

        self.db = Database(mongo_uri)
        self.source_manager = SourceManager()
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Setup Telegram bot application
        builder = Application.builder().token(self.TOKEN)
        self.application = builder.build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start_command)],
            states={
                "handle_urls": [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_urls)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )

        self.application.add_handler(conv_handler)
        logger.info("Telegram bot initialized with handlers.")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"Received /start command from chat_id: {update.effective_chat.id}")
        await update.message.reply_text(
            "Welcome! Please send me the URL(s) of the light novel(s) you want to download. "
            "You can send multiple URLs, each on a new line.\n\n"
            "Send /cancel to end this session."
        )
        return "handle_urls"

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"Received /cancel command from chat_id: {update.effective_chat.id}")
        await update.message.reply_text("Session cancelled.")
        return ConversationHandler.END

    async def handle_urls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        urls = update.message.text.strip().splitlines()
        
        if not urls:
            await update.message.reply_text("Please provide at least one valid URL.")
            return "handle_urls"

        await update.message.reply_text(f"✅ Received {len(urls)} novel(s). Starting the download process. This may take a while...")
        
        loop = asyncio.get_running_loop()
        for url in urls:
            # Run each URL processing in a background thread
            loop.create_task(self.process_single_url(url.strip(), chat_id))
        
        return ConversationHandler.END

    async def process_single_url(self, url: str, chat_id: int):
        bot = self.application.bot
        try:
            await bot.send_message(chat_id, f"🚀 Starting processing for: {url}")

            # 1. Find the correct parser for the URL
            parser = self.source_manager.get_parser_for_url(url)
            if not parser:
                await bot.send_message(chat_id, f"❌ Sorry, no parser found for the website: {url}")
                return

            # 2. Scrape novel info (run synchronous code in a thread)
            await bot.send_message(chat_id, f"🔍 Reading novel information...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, parser.read_novel_info)

            if not parser.chapters:
                await bot.send_message(chat_id, f"❌ Could not find any chapters for '{parser.novel_title}'.")
                return
            
            await bot.send_message(chat_id, f"✅ Found '{parser.novel_title}' with {len(parser.chapters)} chapters. Now downloading content...")

            # 3. Download all chapter bodies (in background threads)
            # This is a simplified approach. A more advanced version would download in batches.
            for chapter in parser.chapters:
                await loop.run_in_executor(self.executor, parser.download_chapter_body, chapter)

            # 4. Build the EPUB file
            await bot.send_message(chat_id, f"📚 Building e-book for '{parser.novel_title}'...")
            builder = EbookBuilder()
            output_filename = f"{parser.novel_title}.epub"
            await loop.run_in_executor(self.executor, builder.build, parser.novel_title, parser.novel_author, parser.novel_cover, parser.chapters, output_filename)

            # 5. Send the file to the user
            await bot.send_message(chat_id, f"🎉 Uploading your e-book!")
            with open(output_filename, 'rb') as epub_file:
                await bot.send_document(chat_id, document=epub_file)
            
            os.remove(output_filename) # Clean up the file from the server

        except Exception as e:
            logger.error(f"Failed to process {url} for chat_id {chat_id}: {e}", exc_info=True)
            await bot.send_message(chat_id, f"❌ An unexpected error occurred while processing {url}.\nError: {e}")
