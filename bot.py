import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from lncrawl.binders.epub import EbookBuilder
from lncrawl.core.sources import get_source_manager

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="telegram_bot")
        self.active_sessions = {}
        self.max_active_sessions = 20
        
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        if not self.TOKEN:
            raise Exception("Telegram token not found")

        # Initialize the SourceManager here
        self.source_manager = get_source_manager()
        
        self.application = Application.builder().token(self.TOKEN).build()
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start_session)],
            states={
                "handle_urls": [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_urls)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_session)],
        )
        self.application.add_handler(conv_handler)

    async def start_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            await update.message.reply_text("You already have an active session. Please /cancel the current one to start a new one.")
            return ConversationHandler.END

        if len(self.active_sessions) >= self.max_active_sessions:
            await update.message.reply_text("The bot is currently busy. Please try again later.")
            return ConversationHandler.END

        self.active_sessions[chat_id] = {"status": "initialized"}
        await update.message.reply_text(
            "Welcome! Please send me the URL(s) of the light novel(s) you want to download. "
            "You can send multiple URLs, each on a new line."
        )
        return "handle_urls"

    async def handle_urls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        urls = update.message.text.strip().splitlines()
        
        valid_urls = [url for url in urls if re.match(r'https?://[^\s]+', url)]
        if not valid_urls:
            await update.message.reply_text("Please provide at least one valid URL.")
            return "handle_urls"

        await update.message.reply_text(f"Processing {len(valid_urls)} novel(s). This may take a while...")

        loop = asyncio.get_event_loop()
        for url in valid_urls:
            # We pass the bot instance and context to the processing function
            loop.run_in_executor(self.executor, self.process_single_url, url, chat_id, self.application.bot)
        
        return ConversationHandler.END

    def process_single_url(self, url, chat_id, bot):
        """This function runs in a separate thread."""
        try:
            parser = self.source_manager.get_parser(url)
            if not parser:
                asyncio.run(bot.send_message(chat_id, text=f"Sorry, the URL {url} is not supported yet."))
                return

            asyncio.run(bot.send_message(chat_id, text=f"Scraping '{url}'..."))
            parser.read_novel_info()

            if not parser.chapters:
                asyncio.run(bot.send_message(chat_id, text=f"Could not find any chapters for '{parser.novel_title}'."))
                return
            
            asyncio.run(bot.send_message(chat_id, text=f"Found {len(parser.chapters)} chapters for '{parser.novel_title}'. Downloading..."))
            
            # Download chapter bodies (this part can be slow)
            for chapter in parser.chapters:
                try:
                    chapter['body'] = parser.download_chapter_body(chapter['url'])
                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter['url']}: {e}")
                    chapter['body'] = "<p><i>Chapter content could not be downloaded.</i></p>"

            asyncio.run(bot.send_message(chat_id, text=f"Building e-book for '{parser.novel_title}'..."))
            
            builder = EbookBuilder()
            # Sanitize the filename to remove characters that are invalid in file names
            safe_title = re.sub(r'[\\/*?:"<>|]', "", parser.novel_title)
            output_filename = f"{safe_title}.epub"
            
            builder.build(
                title=parser.novel_title,
                author=parser.novel_author,
                cover_url=parser.novel_cover,
                chapters=parser.chapters,
                output_path=output_filename
            )

            asyncio.run(bot.send_document(chat_id, document=open(output_filename, 'rb')))
            os.remove(output_filename) # Clean up the file after sending

        except Exception as e:
            logger.error(f"Failed to process {url}: {e}", exc_info=True)
            asyncio.run(bot.send_message(chat_id, text=f"An unexpected error occurred while processing {url}."))
        finally:
            if chat_id in self.active_sessions:
                del self.active_sessions[chat_id]

    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled.")
        return ConversationHandler.END
