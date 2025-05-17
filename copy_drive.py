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

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
SOURCE_CHANNEL = "@Source069"
DESTINATION_CHANNEL = "@Destination07"

# WhatsApp Configuration
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

def clean_whatsapp_text(text):
    """Clean text for WhatsApp while keeping essential formatting"""
    if not text:
        return text
    
    # Simple formatting conversion (preserve *, _, ~, ```)
    return text.replace('\\', '')

async def copy_to_destination(context, message):
    """Send exact copy to destination channel with all formatting"""
    try:
        # Get the raw HTML content of the message
        if hasattr(message, 'text_html'):
            content = message.text_html
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=content,
                parse_mode="HTML"
            )
        elif hasattr(message, 'caption_html') and message.caption_html:
            # For media with caption
            if message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                await context.bot.send_photo(
                    chat_id=DESTINATION_CHANNEL,
                    photo=file.file_id,
                    caption=message.caption_html,
                    parse_mode="HTML"
                )
            elif message.video:
                file = await message.video.get_file()
                await context.bot.send_video(
                    chat_id=DESTINATION_CHANNEL,
                    video=file.file_id,
                    caption=message.caption_html,
                    parse_mode="HTML"
                )
        else:
            # Fallback for non-formatted content
            if message.text:
                await context.bot.send_message(
                    chat_id=DESTINATION_CHANNEL,
                    text=message.text
                )
            elif message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                await context.bot.send_photo(
                    chat_id=DESTINATION_CHANNEL,
                    photo=file.file_id,
                    caption=message.caption if message.caption else None
                )
            elif message.video:
                file = await message.video.get_file()
                await context.bot.send_video(
                    chat_id=DESTINATION_CHANNEL,
                    video=file.file_id,
                    caption=message.caption if message.caption else None
                )
        
        logger.info("Message copied to destination channel with original formatting")
    except Exception as e:
        logger.error(f"Error copying to destination: {str(e)}")

async def send_to_whatsapp(message):
    """Send message to both WhatsApp account and group"""
    try:
        # Prepare content
        whatsapp_text = ""
        if message.text:
            whatsapp_text = clean_whatsapp_text(message.text)
        elif message.caption:
            whatsapp_text = clean_whatsapp_text(message.caption)
        
        # Common payload data
        payload_base = {
            "token": WHATSAPP_API_TOKEN,
            "body": whatsapp_text if whatsapp_text else " "
        }
        
        # Send to WhatsApp account
        payload_account = payload_base.copy()
        payload_account["to"] = WHATSAPP_NUMBER
        
        # Send to WhatsApp group
        payload_group = payload_base.copy()
        payload_group["to"] = WHATSAPP_GROUP_ID
        
        if message.text:
            # Text message
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload_group)
            logger.info("Text sent to WhatsApp")
        
        elif message.photo:
            # Photo with caption
            photo = message.photo[-1]
            file = await photo.get_file()
            payload_account["image"] = file.file_path
            payload_group["image"] = file.file_path
            
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload_group)
            logger.info("Photo sent to WhatsApp")
        
        elif message.video:
            # Video with caption
            file = await message.video.get_file()
            payload_account["video"] = file.file_path
            payload_group["video"] = file.file_path
            
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload_group)
            logger.info("Video sent to WhatsApp")
            
    except Exception as e:
        logger.error(f"Error sending to WhatsApp: {str(e)}")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # 1. Send exact copy to destination channel
            await copy_to_destination(context, message)
            
            # 2. Send to WhatsApp
            await send_to_whatsapp(message)

    except Exception as e:
        logger.error(f"Error in forward_message: {str(e)}")

async def post_init(application: Application) -> None:
    """Initialization"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Ready for polling")

def run_bot():
    """Run the Telegram bot"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    application.add_handler(MessageHandler(filters.ALL, forward_message))
    
    application.run_polling(
        close_loop=False,
        stop_signals=[],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    # Single instance check
    if os.environ.get("_BOT_RUNNING") == "1":
        logger.error("Another instance already running")
        exit(1)
    
    os.environ["_BOT_RUNNING"] = "1"
    
    try:
        # Start bot
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Start Flask
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["_BOT_RUNNING"] = "0"
