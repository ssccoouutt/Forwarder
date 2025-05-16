import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import re
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
WHATSAPP_NUMBER = "923247220362"  # Your linked number
WHATSAPP_GROUP_ID = "120363140590753276@g.us"  # Target group
ULTRA_MSG_BASE_URL = f"https://api.ultramsg.com/{WHATSAPP_INSTANCE_ID}"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def clean_whatsapp_text(text):
    """Clean text for WhatsApp while preserving essential formatting"""
    if not text:
        return text
    
    # Remove Telegram escapes but keep WhatsApp formatting
    text = re.sub(r'\\([._*~`])', r'\1', text)
    
    # Convert Telegram formatting to WhatsApp
    text = re.sub(r'<b>(.*?)</b>', r'*\1*', text)  # bold
    text = re.sub(r'<i>(.*?)</i>', r'_\1_', text)  # italic
    text = re.sub(r'<u>(.*?)</u>', r'~\1~', text)  # underline/strikethrough
    text = re.sub(r'<code>(.*?)</code>', r'```\1```', text)  # code
    
    # Remove quote formatting for WhatsApp
    text = re.sub(r'^>\s?(.*)$', r'\1', text, flags=re.MULTILINE)
    
    return text

async def send_to_destination(context, message):
    """Send exact copy to destination channel (not forwarded)"""
    try:
        if message.text:
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=message.text_markdown_v2 or message.text,
                parse_mode='MarkdownV2'
            )
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(
                chat_id=DESTINATION_CHANNEL,
                photo=file.file_id,
                caption=message.caption_markdown_v2 if message.caption else None,
                parse_mode='MarkdownV2'
            )
        elif message.video:
            file = await message.video.get_file()
            await context.bot.send_video(
                chat_id=DESTINATION_CHANNEL,
                video=file.file_id,
                caption=message.caption_markdown_v2 if message.caption else None,
                parse_mode='MarkdownV2'
            )
        logger.info("Message copied to destination channel")
    except Exception as e:
        logger.error(f"Error sending to destination: {str(e)}")

async def send_to_whatsapp(message):
    """Send message to both WhatsApp account and group"""
    try:
        # Prepare content
        whatsapp_text = ""
        if message.text:
            whatsapp_text = clean_whatsapp_text(message.text_markdown_v2 or message.text)
        elif message.caption:
            whatsapp_text = clean_whatsapp_text(message.caption_markdown_v2 or message.caption)
        
        if not whatsapp_text:
            return
            
        # Send to WhatsApp account
        payload_account = {
            "token": WHATSAPP_API_TOKEN,
            "to": WHATSAPP_NUMBER,
            "body": whatsapp_text
        }
        
        # Send to WhatsApp group
        payload_group = {
            "token": WHATSAPP_API_TOKEN,
            "to": WHATSAPP_GROUP_ID,
            "body": whatsapp_text
        }
        
        if message.text:
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload_group)
            logger.info("Text sent to WhatsApp account and group")
        
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            payload_account["image"] = file.file_path
            payload_account["caption"] = whatsapp_text
            payload_group["image"] = file.file_path
            payload_group["caption"] = whatsapp_text
            
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload_group)
            logger.info("Photo sent to WhatsApp account and group")
        
        elif message.video:
            file = await message.video.get_file()
            payload_account["video"] = file.file_path
            payload_account["caption"] = whatsapp_text
            payload_group["video"] = file.file_path
            payload_group["caption"] = whatsapp_text
            
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload_account)
            requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload_group)
            logger.info("Video sent to WhatsApp account and group")
            
    except Exception as e:
        logger.error(f"Error sending to WhatsApp: {str(e)}")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # 1. Send exact copy to destination channel
            await send_to_destination(context, message)
            
            # 2. Send to WhatsApp (both account and group)
            await send_to_whatsapp(message)

    except Exception as e:
        logger.error(f"Error in forward_message: {str(e)}")

async def post_init(application: Application) -> None:
    """Initialization"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted and ready for polling")

def run_bot():
    """Run the Telegram bot in its own event loop"""
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
    # Check if another instance is already running
    if os.environ.get("_BOT_RUNNING") == "1":
        logger.error("Another bot instance is already running")
        exit(1)
    
    os.environ["_BOT_RUNNING"] = "1"
    
    try:
        # Start Telegram bot in a separate thread
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Start Flask server
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["_BOT_RUNNING"] = "0"
