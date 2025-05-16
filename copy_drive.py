import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import re

app = Flask(__name__)

# Configuration (HARDCODED)
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
SOURCE_CHANNEL = "@Source069"
DESTINATION_CHANNEL = "@Destination07"
WHATSAPP_API_TOKEN = "j0253a3npbpb7ikw"
WHATSAPP_INSTANCE_ID = "instance116714"
WHATSAPP_NUMBER = "923247220362"
ULTRA_MSG_BASE_URL = f"https://api.ultramsg.com/{WHATSAPP_INSTANCE_ID}"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def convert_telegram_to_whatsapp(text):
    """Convert Telegram formatting to WhatsApp formatting"""
    if not text:
        return text
    
    # Convert bold (**text** or __text__) to *text*
    text = re.sub(r'(\*\*|__)(.*?)\1', r'*\2*', text)
    
    # Convert italic (*text* or _text_) to _text_
    text = re.sub(r'(?<!\*)(\*|_)(.*?)\1(?!\*)', r'_\2_', text)
    
    # Convert code (`text`) to ```text```
    text = re.sub(r'`(.*?)`', r'```\1```', text)
    
    return text

async def copy_message_without_forward(chat_id, from_chat_id, message_id, bot):
    """Copy message without forwarded tag"""
    message = await bot.get_message(from_chat_id, message_id)
    
    if message.text:
        return await bot.send_message(chat_id=chat_id, text=message.text)
    elif message.photo:
        photo = message.photo[-1]
        file = await photo.get_file()
        return await bot.send_photo(
            chat_id=chat_id,
            photo=file.file_path,
            caption=message.caption
        )
    elif message.video:
        file = await message.video.get_file()
        return await bot.send_video(
            chat_id=chat_id,
            video=file.file_path,
            caption=message.caption
        )

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # Copy to destination channel without forwarded tag
            await copy_message_without_forward(
                chat_id=DESTINATION_CHANNEL,
                from_chat_id=SOURCE_CHANNEL,
                message_id=message.message_id,
                bot=context.bot
            )
            logger.info("Message copied to Telegram channel")
            
            # Prepare WhatsApp message
            whatsapp_text = ""
            if message.text:
                whatsapp_text = convert_telegram_to_whatsapp(message.text)
            elif message.caption:
                whatsapp_text = convert_telegram_to_whatsapp(message.caption)
            
            # Send to WhatsApp
            if whatsapp_text:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "body": whatsapp_text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
                logger.info("Text sent to WhatsApp")
            
            if message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "image": file.file_path,
                    "caption": whatsapp_text if whatsapp_text else ""
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
                logger.info("Photo sent to WhatsApp")
            
            if message.video:
                file = await message.video.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "video": file.file_path,
                    "caption": whatsapp_text if whatsapp_text else ""
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
                logger.info("Video sent to WhatsApp")

    except Exception as e:
        logger.error(f"Error in forward_message: {str(e)}")

def run_bot():
    """Run the Telegram bot in its own event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, forward_message))
    
    # Disable signal handling since we're not in main thread
    application.run_polling(close_loop=False, stop_signals=[])

if __name__ == '__main__':
    # Start Telegram bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=8000, use_reloader=False)
