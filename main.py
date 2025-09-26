import os
import asyncio
from flask import Flask, request
from telegram import Update
from bot import TelegramBot  # Import the bot from the new file
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the bot once
telegram_bot = TelegramBot()

# Initialize Flask app
app = Flask(__name__)

@app.route(f"/{telegram_bot.TOKEN}", methods=["POST"])
def webhook():
    """This endpoint receives updates from Telegram."""
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, telegram_bot.application.bot)
    
    # Process the update in a non-blocking way
    asyncio.run(telegram_bot.application.process_update(update))
    
    return "ok"

# This part is only for local testing and should NOT be run on Render
if __name__ == '__main__':
    print("This script is meant to be run by a Gunicorn server in production.")
    print("It does not set the webhook. Use 'run_webhook.py' for that.")
