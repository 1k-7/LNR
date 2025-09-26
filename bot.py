import os
import asyncio
import traceback
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from lncrawl.core.sources import get_parser_for_url
from lncrawl.binders.epub import EbookBuilder
from lncrawl.database import Database

# Helper to sanitize filenames
def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

class TelegramBot:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="telegram_bot")
        self.active_sessions = {}
        
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        if not self.TOKEN:
            raise Exception("FATAL: TELEGRAM_TOKEN not found in environment variables.")

        mongo_uri = os.getenv("MONGO_URI")
        self.db = Database(mongo_uri) if mongo_uri else None
        
        self.application = Application.builder().token(self.TOKEN).build()
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.init_app)],
            states={
                "handle_urls": [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_urls)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_session)],
        )
        self.application.add_handler(conv_handler)

    async def init_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id in self.active_sessions:
            await update.message.reply_text("You have a job in progress. Please wait for it to complete or /cancel it.")
            return ConversationHandler.END

        self.active_sessions[chat_id] = True
        await update.message.reply_text("Welcome! Send me a URL of a light novel to download as an EPUB.")
        return "handle_urls"

    async def handle_urls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        urls = update.message.text.strip().splitlines()
        
        await update.message.reply_text(f"Accepted {len(urls)} novel(s). Processing will begin shortly...")

        # Use the application's job queue for better integration and persistence
        for url in urls:
            context.job_queue.run_once(self.run_download_job, 1, data={'chat_id': chat_id, 'url': url}, name=f"job_{chat_id}_{url}")
        
        return ConversationHandler.END

    @staticmethod
    async def run_download_job(context: ContextTypes.DEFAULT_TYPE):
        job_data = context.job.data
        chat_id = job_data['chat_id']
        url = job_data['url']
        bot = context.bot
        
        try:
            await bot.send_message(chat_id, text=f"🚀 Starting: {url}")
            
            ParserClass = get_parser_for_url(url)
            if not ParserClass:
                await bot.send_message(chat_id, text=f"❌ Unsupported Site: {url}")
                return

            parser = ParserClass(url)
            parser.read_novel_info()
            
            await bot.send_message(chat_id, text=f"Downloading '{parser.novel_title}' ({len(parser.chapters)} chapters)...")
            
            downloaded_chapters = []
            for i, chapter in enumerate(parser.chapters):
                # Limit to 5 chapters for testing; remove [:5] for full download
                if i >= 5: 
                    break
                chapter['body'] = parser.download_chapter_body(chapter['url'])
                downloaded_chapters.append(chapter)

            if not downloaded_chapters:
                raise Exception("No chapters were downloaded.")

            await bot.send_message(chat_id, text=f"📚 Creating e-book...")

            builder = EbookBuilder()
            output_filename = f"{sanitize_filename(parser.novel_title)}.epub"
            
            builder.build(
                title=parser.novel_title, author=parser.novel_author,
                cover_url=parser.novel_cover, chapters=downloaded_chapters,
                output_path=output_filename
            )
            
            await bot.send_message(chat_id, text=f"✅ Uploading '{output_filename}'...")
            
            with open(output_filename, 'rb') as f:
                await bot.send_document(chat_id, document=f, filename=output_filename)
            
            os.remove(output_filename)

        except Exception as e:
            error_message = f"❌ Failed to process {url}.\nError: {e}"
            print(error_message)
            traceback.print_exc()
            await bot.send_message(chat_id, text=error_message)

    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled. You can start a new one with /start.")
        return ConversationHandler.END
