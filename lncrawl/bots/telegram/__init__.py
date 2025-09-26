import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from lncrawl.core.app import App
from lncrawl.database import Database
from lncrawl.core.sources import get_parser_for_url
from lncrawl.binders.epub import EbookBuilder # We need a way to build the ebook

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
        # Your webhook setup remains the same
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
            # Run each URL process in a separate thread
            loop.run_in_executor(self.executor, self.process_single_url, url, chat_id)
        
        return ConversationHandler.END

    def process_single_url(self, url, chat_id):
        # This is where the magic happens!
        asyncio.run(self.application.bot.send_message(chat_id, text=f"Starting download for: {url}"))
        
        ParserClass = get_parser_for_url(url)
        if not ParserClass:
            asyncio.run(self.application.bot.send_message(chat_id, text=f"Sorry, the site for this URL is not supported: {url}"))
            return

        try:
            # 1. Initialize the correct parser
            parser = ParserClass(url)
            
            # 2. Scrape novel info and chapter list
            parser.read_novel_info()
            
            # 3. Download all chapter bodies
            # (In a real app, you'd let the user select chapters)
            for chapter in parser.chapters:
                chapter['body'] = parser.download_chapter_body(chapter['url'])
            
            # 4. Build the EPUB file
            ebook = EbookBuilder()
            # The builder needs more parameters, this is a simplified example
            # You would pass novel title, author, cover, chapters etc.
            # ebook.title = parser.novel_title
            # ebook.author = parser.novel_author
            # ebook.chapters = parser.chapters
            # output_path = ebook.write() # This would create the file

            # For now, we'll just simulate success and send a message
            # In a real app, you would send the actual file:
            # context.bot.send_document(chat_id, document=open(output_path, 'rb'))
            message = f"✅ Successfully processed: {parser.novel_title}"
            asyncio.run(self.application.bot.send_message(chat_id, text=message))

        except Exception as e:
            error_message = f"❌ Failed to process {url}. Error: {e}"
            print(error_message)
            asyncio.run(self.application.bot.send_message(chat_id, text=error_message))


    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled.")
        return ConversationHandler.END
