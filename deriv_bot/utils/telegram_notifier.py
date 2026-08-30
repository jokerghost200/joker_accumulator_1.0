import os
import requests
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logger = logging.getLogger("utils.telegram")

def _send_message_blocking(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram configuration missing. Message not sent.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200:
            logger.error(f"Failed to send Telegram message: {response.status_code} {response.text}")
        else:
            logger.debug("Telegram message sent successfully.")
    except requests.exceptions.Timeout:
        logger.warning("Telegram request timed out. Ignoring to avoid blocking.")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Telegram API request failed: {e}")
    except Exception as e:
        logger.error(f"Exception while sending Telegram message: {e}")


async def send_telegram_message(message: str):
    """Sends a message to the configured Telegram chat asynchronously without blocking the loop."""
    try:
        await asyncio.to_thread(_send_message_blocking, message)
    except Exception as e:
        logger.error(f"Failed to schedule Telegram message: {e}")

def send_telegram_message_sync(message: str):
    """Utility to run the async send_telegram_message in a new loop if needed."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_telegram_message(message))
    except RuntimeError:
        _send_message_blocking(message)
