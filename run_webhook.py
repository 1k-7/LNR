import os
import asyncio
from telegram.ext import Application
from dotenv import load_dotenv

async def main():
    """
    A simple one-time script to set the Telegram webhook.
    """
    # Load environment variables from a .env file
    load_dotenv()

    TOKEN = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN not found in .env file.")
        return
    if not WEBHOOK_URL:
        print("ERROR: WEBHOOK_URL not found in .env file. This should be your Render service URL.")
        return

    # The full URL for the webhook must include the token path
    full_webhook_url = f"{WEBHOOK_URL}/{TOKEN}"

    print(f"Setting webhook for bot...")
    print(f"URL: {full_webhook_url}")

    # Create a dummy application instance just to access the bot object
    application = Application.builder().token(TOKEN).build()

    # Set the webhook
    await application.bot.set_webhook(url=full_webhook_url)

    # Verify the webhook was set
    webhook_info = await application.bot.get_webhook_info()
    print("\n--- Webhook Info ---")
    print(f"URL: {webhook_info.url}")
    print(f"Pending Updates: {webhook_info.pending_update_count}")
    print(f"Last Error: {webhook_info.last_error_message or 'None'}")
    print("--------------------")

    if webhook_info.url == full_webhook_url:
        print("\n✅ Webhook set successfully!")
        print("Your bot is now live and should respond to /start.")
    else:
        print("\n❌ Failed to set webhook.")

if __name__ == '__main__':
    asyncio.run(main())
