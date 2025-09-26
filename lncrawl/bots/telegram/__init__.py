import os
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from lncrawl.core.app import App
from lncrawl.database import Database
from lncrawl.core.sources import get_parser_for_url
from lncrawl.binders.epub import EbookBuilder

class TelegramBot:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="telegram_bot")
        self.active_sessions = {}
        
        self.TOKEN = os.getenv("TELEGRAM_TOKEN", "")
        if not self.TOKEN:
            raise Exception("Telegram token not found")

        self.db = Database(os.getenv("MONGO_URI"))
        
        self.application = Application.builder().token(self.TOKEN).build()
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.init_app)],
            states={
                "handle_urls": [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_urls)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_session)],
        )
        self.application.add_handler(conv_handler)

    def start_webhook(self, webhook_url):
        # Your webhook setup code would go here. For now, it's a placeholder.
        # This will need to be implemented for web service deployment.
        pass

    async def init_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            await update.message.reply_text("You already have an active session. Please /cancel the current one to start a new one.")
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
        
        if not urls:
            await update.message.reply_text("Please provide at least one URL.")
            return "handle_urls"

        await update.message.reply_text(f"Accepted {len(urls)} novel(s) for processing. I will send them as they become available.")

        loop = asyncio.get_event_loop()
        for url in urls:
            # Pass the bot instance to the thread
            loop.run_in_executor(self.executor, self.process_single_url, url, chat_id, self.application.bot)
        
        return ConversationHandler.END

    def process_single_url(self, url, chat_id, bot):
        # This function runs in a separate thread.
        # It needs its own event loop to call async bot methods.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(bot.send_message(chat_id, text=f"🚀 Starting download for: {url}"))
            
            ParserClass = get_parser_for_url(url)
            if not ParserClass:
                loop.run_until_complete(bot.send_message(chat_id, text=f"❌ Sorry, the site for this URL is not supported: {url}"))
                return

            # 1. Scrape data
            parser = ParserClass(url)
            parser.read_novel_info()
            
            loop.run_until_complete(bot.send_message(chat_id, text=f"Found '{parser.novel_title}' with {len(parser.chapters)} chapters. Downloading content..."))
            
            # Here, we'll just download the first 5 chapters for a quick test.
            # Remove the '[:5]' to download all chapters.
            chapters_to_download = parser.chapters[:5] 
            for chapter in chapters_to_download:
                chapter['body'] = parser.download_chapter_body(chapter['url'])
            
            loop.run_until_complete(bot.send_message(chat_id, text=f"📚 Download complete. Now creating your e-book..."))

            # 2. Build the EPUB file
            builder = EbookBuilder()
            output_filename = f"{parser.novel_title}.epub"
            
            builder.build(
                title=parser.novel_title,
                author=parser.novel_author,
                cover_url=parser.novel_cover,
                chapters=chapters_to_download,
                output_path=output_filename
            )
            
            loop.run_until_complete(bot.send_message(chat_id, text=f"✅ E-book created! Uploading now..."))
            
            # 3. Send the file
            with open(output_filename, 'rb') as f:
                loop.run_until_complete(bot.send_document(chat_id, document=f, filename=output_filename))
            
            # 4. Clean up the created file
            os.remove(output_filename)

        except Exception as e:
            error_message = f"❌ Failed to process {url}.\nError: {e}"
            print(error_message)
            traceback.print_exc() # For detailed debugging in your server logs
            loop.run_until_complete(bot.send_message(chat_id, text=error_message))
        finally:
            loop.close()

    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled.")
        return ConversationHandler.END
