import os
import asyncio
from flask import Flask, request
from telegram import Update
from bot import TelegramBot # Import the bot from bot.py
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize the bot
bot = TelegramBot()

@app.route("/")
def index():
    """A simple page to confirm the web server is running."""
    return "Hello, I am the LNR bot!"

@app.route(f"/{bot.TOKEN}", methods=["POST"])
def webhook():
    """This endpoint receives updates from Telegram."""
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, bot.application.bot)
    # Using asyncio.run to handle the async process_update method
    asyncio.run(bot.application.process_update(update))
    return "ok"

@app.route('/setup')
def setup_webhook():
    """
    A one-time setup page to link the bot with Telegram.
    Visit this URL in your browser once after deploying.
    """
    try:
        # The set_webhook function needs to be async
        async def set_hook():
            webhook_url = os.getenv("WEBHOOK_URL")
            if not webhook_url:
                return "Error: WEBHOOK_URL environment variable not set!"
            
            full_webhook_url = f"{webhook_url}/{bot.TOKEN}"
            success = await bot.application.bot.set_webhook(full_webhook_url)
            if success:
                return f"Webhook set successfully to: {full_webhook_url}"
            else:
                return "Webhook setup failed!"
        
        # Run the async function
        return asyncio.run(set_hook())

    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    # This part is for local testing and will not be used on Render
    app.run(debug=True)
