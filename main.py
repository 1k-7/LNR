import os
from flask import Flask, request
from telegram import Update
from lncrawl.bots.telegram import TelegramBot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the bot and its application
bot = TelegramBot()

# Initialize Flask app
app = Flask(__name__)

@app.route(f"/{bot.TOKEN}", methods=["POST"])
def webhook():
    """This endpoint receives updates from Telegram."""
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    bot.application.process_update(update)
    return "ok"

# The following block is for local testing and should not run on Render
if __name__ == "__main__":
    # In a production environment like Render, Gunicorn runs the 'app' object directly.
    # The webhook needs to be set MANUALLY once.
    # You can do this by running a small script or visiting a specific URL.
    # For now, we assume the webhook is already set.
    print("Flask app is ready. To run locally, use a WSGI server like Waitress or Gunicorn.")
    print(f"Webhook endpoint is at: /<{bot.TOKEN}>")
