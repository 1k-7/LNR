import os
import asyncio
from flask import Flask, request, render_template_string
from telegram import Update
from bot import TelegramBot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the bot once
bot = TelegramBot()
app = Flask(__name__)

@app.route(f"/{bot.TOKEN}", methods=["POST"])
def webhook():
    """This endpoint receives updates from Telegram."""
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    asyncio.run(bot.application.process_update(update))
    return "ok", 200

@app.route("/setup")
async def setup_webhook():
    """
    A one-time setup page to link the bot with Telegram.
    Visit this page in your browser once after deploying.
    """
    try:
        WEBHOOK_URL = os.getenv("WEBHOOK_URL")
        if not WEBHOOK_URL:
            return "<html><body><h1>Error</h1><p>WEBHOOK_URL environment variable is not set.</p></body></html>", 500

        full_webhook_url = f"{WEBHOOK_URL}/{bot.TOKEN}"
        
        await bot.application.bot.set_webhook(url=full_webhook_url)
        info = await bot.application.bot.get_webhook_info()
        
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Webhook Setup</title>
            <style>
                body { font-family: sans-serif; padding: 2em; }
                code { background-color: #eee; padding: 3px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>✅ Webhook Setup Successful!</h1>
            <p>Your bot is now linked to Telegram.</p>
            <h3>Details:</h3>
            <ul>
                <li>URL: <code>{{ info.url }}</code></li>
                <li>Pending Updates: <code>{{ info.pending_update_count }}</code></li>
                <li>Last Error: <code>{{ info.last_error_message or 'None' }}</code></li>
            </ul>
            <p>You can now go to your Telegram chat and send <b>/start</b>.</p>
        </body>
        </html>
        """, info=info)

    except Exception as e:
        return f"<html><body><h1>❌ Webhook Setup Failed</h1><p>Error: {e}</p></body></html>", 500

if __name__ == '__main__':
    print("This script is meant to be run by a Gunicorn server in production.")
