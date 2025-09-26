import asyncio
import os
import logging
from flask import Flask, request
from telegram import Update
from bot import TelegramBot
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Flask app and the bot
app = Flask(__name__)
bot = TelegramBot()

@app.route(f"/{bot.TOKEN}", methods=["POST"])
async def webhook():
    """Endpoint that Telegram sends updates to."""
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    await bot.application.process_update(update)
    return "ok"

@app.route("/setup")
async def setup_webhook():
    """One-time setup page to register the webhook with Telegram."""
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        return "ERROR: WEBHOOK_URL environment variable not set!", 500
    
    full_webhook_url = f"{webhook_url}/{bot.TOKEN}"
    
    try:
        success = await bot.application.bot.set_webhook(full_webhook_url)
        if success:
            logger.info("Webhook set successfully!")
            return "Webhook Setup Successful!", 200
        else:
            logger.error("Webhook setup failed.")
            return "Webhook Setup Failed!", 500
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return f"An error occurred: {e}", 500

if __name__ == "__main__":
    # This part is for local development and will not be used on Render.
    # Render uses the CMD from the Dockerfile to run the application.
    logger.info("This script is not meant to be run directly in production.")
