import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import os

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

# Configuration
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
SOURCE_CHANNEL = "@Source069"
DESTINATION_CHANNEL = "@Destination07"
WHATSAPP_API_TOKEN = "j0253a3npbpb7ikw"
WHATSAPP_INSTANCE_ID = "instance116714"
WHATSAPP_NUMBER = "923247220362"
WHATSAPP_GROUP_ID = "120363140590753276@g.us"
ULTRA_MSG_BASE_URL = f"https://api.ultramsg.com/{WHATSAPP_INSTANCE_ID}"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def forward_to_destination(context, message):
    """Forward message to destination channel with original formatting"""
    try:
        # For text messages
        if message.text:
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=message.text,
                parse_mode=None  # Let Telegram handle formatting automatically
            )
        # For photos with caption
        elif message.photo and message.caption:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(
                chat_id=DESTINATION_CHANNEL,
                photo=file.file_id,
                caption=message.caption,
                parse_mode=None
            )
        # For photos without caption
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(
                chat_id=DESTINATION_CHANNEL,
                photo=file.file_id
            )
        # For videos with caption
        elif message.video and message.caption:
            file = await message.video.get_file()
            await context.bot.send_video(
                chat_id=DESTINATION_CHANNEL,
                video=file.file_id,
                caption=message.caption,
                parse_mode=None
            )
        # For videos without caption
        elif message.video:
            file = await message.video.get_file()
            await context.bot.send_video(
                chat_id=DESTINATION_CHANNEL,
                video=file.file_id
            )
        logger.info("Message forwarded to destination channel")
    except Exception as e:
        logger.error(f"Error forwarding to destination: {str(e)}")

async def send_to_whatsapp(message):
    """Send message to WhatsApp account and group"""
    try:
        # Prepare text content
        whatsapp_text = ""
        if message.text:
            whatsapp_text = message.text
        elif message.caption:
            whatsapp_text = message.caption
        
        # Prepare media content
        media_url = None
        if message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            media_url = file.file_path
        elif message.video:
            file = await message.video.get_file()
            media_url = file.file_path
        
        # Send to WhatsApp account
        if message.text:
            payload = {
                "token": WHATSAPP_API_TOKEN,
                "to": WHATSAPP_NUMBER,
                "body": whatsapp_text
            }
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
        elif media_url:
            if message.photo:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "image": media_url,
                    "caption": whatsapp_text if whatsapp_text else " "
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
            elif message.video:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "video": media_url,
                    "caption": whatsapp_text if whatsapp_text else " "
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
        
        # Send to WhatsApp group (same as above but with group ID)
        if message.text:
            payload = {
                "token": WHATSAPP_API_TOKEN,
                "to": WHATSAPP_GROUP_ID,
                "body": whatsapp_text
            }
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
        elif media_url:
            if message.photo:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_GROUP_ID,
                    "image": media_url,
                    "caption": whatsapp_text if whatsapp_text else " "
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
            elif message.video:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_GROUP_ID,
                    "video": media_url,
                    "caption": whatsapp_text if whatsapp_text else " "
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
        
        logger.info("Message sent to WhatsApp")
    except Exception as e:
        logger.error(f"Error sending to WhatsApp: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # Forward to destination channel
            await forward_to_destination(context, message)
            
            # Send to WhatsApp
            await send_to_whatsapp(message)
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

async def post_init(application: Application):
    """Initialize bot"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot initialized")

def run_bot():
    """Run Telegram bot"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    application.run_polling()

if __name__ == '__main__':
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=8000)
