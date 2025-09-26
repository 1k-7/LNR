import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from bot import TelegramBot
from dotenv import load_dotenv

# --- Initialization ---
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create bot and app instances
bot = TelegramBot()
app = Flask(__name__)

@app.route(f"/{bot.TOKEN}", methods=["POST"])
def webhook():
    """Endpoint that Telegram sends updates to."""
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    # Run the async update processing in a new event loop
    asyncio.run(bot.application.process_update(update))
    return "ok"

@app.route("/setup")
def setup_webhook():
    """One-time setup page to register the webhook with Telegram."""
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        return "ERROR: WEBHOOK_URL environment variable not set!", 500
    
    full_webhook_url = f"{webhook_url}/{bot.TOKEN}"
    
    try:
        # Run the async set_webhook call in a new event loop
        success = asyncio.run(bot.application.bot.set_webhook(full_webhook_url))
        if success:
            logger.info("Webhook set successfully!")
            return "Webhook Setup Successful!", 200
        else:
            logger.error("Webhook setup failed.")
            return "Webhook Setup Failed!", 500
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return f"An error occurred: {e}", 500

# Note: The Gunicorn command in the Dockerfile is the production entry point.
# This __name__ == "__main__" block is not used on Render.
