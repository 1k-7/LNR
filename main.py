import os
from flask import Flask, request
from telegram import Update
from lncrawl.bots.telegram import TelegramBot
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
bot = TelegramBot()

@app.route(f"/{bot.TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    bot.application.process_update(update)
    return "ok"

if __name__ == "__main__":
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        raise Exception("WEBHOOK_URL not found in environment variables")
    bot.start_webhook(WEBHOOK_URL)