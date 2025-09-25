import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from flask import Flask, request

from lncrawl.core.app import App
from lncrawl.database import Database
from sources.en.w.wuxiaworldco import WuxiaworldCoParser # Example parser

class TelegramBot:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="telegram_bot")
        self.active_sessions = {}
        self.max_active_sessions = 50
        
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
        self.application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=self.TOKEN,
            webhook_url=f"{webhook_url}/{self.TOKEN}"
        )

    async def init_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        if not urls:
            await update.message.reply_text("Please provide at least one URL.")
            return "handle_urls"

        await update.message.reply_text(f"Processing {len(urls)} novel(s). This might take a while...")

        loop = asyncio.get_event_loop()
        for url in urls:
            loop.run_in_executor(self.executor, self.process_single_url, url, chat_id)
        
        return ConversationHandler.END

    def process_single_url(self, url, chat_id):
        # This is a simplified example. You would expand this to handle downloads, formats, etc.
        try:
            # Here you would add logic to select the correct parser based on the URL
            # For this example, we'll just use the WuxiaworldCoParser
            if "wuxiaworld.co" in url:
                parser = WuxiaworldCoParser(url)
                parser.read_novel_info()
                
                # For demonstration, we'll just send the novel title and number of chapters
                message = f"Novel: {parser.novel_title}\nChapters Found: {len(parser.chapters)}"
                asyncio.run(self.application.bot.send_message(chat_id, text=message))
            else:
                asyncio.run(self.application.bot.send_message(chat_id, text=f"Sorry, the URL {url} is not supported yet."))

        except Exception as e:
            asyncio.run(self.application.bot.send_message(chat_id, text=f"Failed to process {url}. Error: {e}"))


    async def cancel_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_message.chat_id)
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
        await update.message.reply_text("Session cancelled.")
        return ConversationHandler.END