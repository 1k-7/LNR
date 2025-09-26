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

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

class TelegramBot:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.active_sessions = {}
        
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        if not self.TOKEN:
            raise Exception("FATAL: TELEGRAM_TOKEN not found.")

        self.db = Database(os.getenv("MONGO_URI")) if os.getenv("MONGO_URI") else None
        
        self.application = Application.builder().token(self.TOKEN).build()
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.init_app)],
            states={ "handle_urls": [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_urls)] },
            fallbacks=[CommandHandler("cancel", self.cancel_session)],
        )
        self.application.add_handler(conv_handler)

    async def init_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id in self.active_sessions:
            await update.message.reply_text("You have a job in progress. Please wait for it to complete.")
            return ConversationHandler.END

        self.active_sessions[chat_id] = True
        await update.message.reply_text("Welcome! Send me the URL of a light novel to download.")
        return "handle_urls"

    async def handle_urls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        urls = update.message.text.strip().splitlines()
        
        await update.message.reply_text(f"Accepted {len(urls)} novel(s) for processing.")
        
        loop = asyncio.get_running_loop()
        for url in urls:
            loop.run_in_executor(self.executor, self.process_single_url, url, chat_id, self.application.bot)
        
        return ConversationHandler.END

    def process_single_url(self, url, chat_id, bot):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(bot.send_message(chat_id, text=f"🚀 Starting: {url}"))
            ParserClass = get_parser_for_url(url)
            if not ParserClass:
                loop.run_until_complete(bot.send_message(chat_id, text=f"❌ Unsupported Site: {url}"))
                return

            parser = ParserClass(url)
            parser.read_novel_info()
            
            loop.run_until_complete(bot.send_message(chat_id, text=f"Downloading '{parser.novel_title}'..."))
            
            for chapter in parser.chapters:
                chapter['body'] = parser.download_chapter_body(chapter['url'])

            loop.run_until_complete(bot.send_message(chat_id, text=f"📚 Creating e-book..."))

            builder = EbookBuilder()
            output_filename = f"{sanitize_filename(parser.novel_title)}.epub"
            
            builder.build(
                title=parser.novel_title, author=parser.novel_author,
                cover_url=parser.novel_cover, chapters=parser.chapters,
                output_path=output_filename
            )
            
            loop.run_until_complete(bot.send_message(chat_id, text=f"✅ Uploading '{output_filename}'..."))
            
            with open(output_filename, 'rb') as f:
                loop.run_until_complete(bot.send_document(chat_id, document=f, filename=output_filename))
            
            os.remove(output_filename)

        except Exception:
            error_message = f"❌ Failed to process {url}.\nError:\n{traceback.format_exc()}"
            print(error_message)
            loop.run_until_complete(bot.send_message(chat_id, text=error_message))
        finally:
            self.active_sessions.pop(chat_id, None)
            loop.close()

    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled. You can start a new one with /start.")
        return ConversationHandler.END
