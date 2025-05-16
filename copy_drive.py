import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import re
import os

# Initialize Flask app for Koyeb health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
SOURCE_CHANNEL = "@Source069"
DESTINATION_CHANNEL = "@Destination07"

# UltraMSG Configuration
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

def clean_escapes(text):
    """Remove unnecessary escape characters from Telegram's MarkdownV2"""
    if not text:
        return text
    # Remove escapes before these characters: . - _ * [ ] ( ) ~ ` > # + = | { } ! 
    return re.sub(r'\\([._*\[\]()~`>#+=|{}!-])', r'\1', text)

def convert_telegram_to_whatsapp(text):
    """Convert Telegram formatting to WhatsApp formatting"""
    if not text:
        return text
    
    # First clean escape characters
    text = clean_escapes(text)
    
    # Handle quotes (remove formatting for WhatsApp)
    text = re.sub(r'^>\s?(.*)$', r'\1', text, flags=re.MULTILINE)
    
    # Replace formatting
    replacements = [
        (r'<b>(.*?)</b>', r'*\1*'),      # bold
        (r'<strong>(.*?)</strong>', r'*\1*'),
        (r'<i>(.*?)</i>', r'_\1_'),      # italic
        (r'<em>(.*?)</em>', r'_\1_'),
        (r'<u>(.*?)</u>', r'~\1~'),      # underline
        (r'<s>(.*?)</s>', r'~\1~'),      # strikethrough
        (r'<del>(.*?)</del>', r'~\1~'),
        (r'<code>(.*?)</code>', r'```\1```'),
        (r'<pre>(.*?)</pre>', r'```\1```')
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    
    return text

async def send_copy_to_destination(context, message):
    """Send a copy of the message to destination channel with original formatting"""
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
        logger.info("Message copied to destination channel with original formatting")
    except Exception as e:
        logger.error(f"Error sending copy to destination: {str(e)}")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # Send copy to destination channel with original formatting
            await send_copy_to_destination(context, message)
            
            # Prepare WhatsApp content
            whatsapp_text = ""
            if message.text:
                whatsapp_text = convert_telegram_to_whatsapp(message.text_markdown_v2 or message.text)
            elif message.caption:
                whatsapp_text = convert_telegram_to_whatsapp(message.caption_markdown_v2 or message.caption)
            
            # Send to WhatsApp
            if message.text:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "body": whatsapp_text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
                logger.info("Text sent to WhatsApp")
            
            elif message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "image": file.file_path,
                    "caption": whatsapp_text if whatsapp_text else None
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
                logger.info("Photo sent to WhatsApp")
            
            elif message.video:
                file = await message.video.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "video": file.file_path,
                    "caption": whatsapp_text if whatsapp_text else None
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
                logger.info("Video sent to WhatsApp")

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
    
    # Disable signal handling since we're not in main thread
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
