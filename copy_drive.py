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
WHATSAPP_NUMBER = "923247220362"
WHATSAPP_GROUP_ID = "120363140590753276"  # Added WhatsApp group ID
ULTRA_MSG_BASE_URL = f"https://api.ultramsg.com/{WHATSAPP_INSTANCE_ID}"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def clean_whatsapp_text(text):
    """Clean text for WhatsApp by removing Telegram-specific escapes"""
    if not text:
        return text
    # Remove escapes before these characters: . - _ * [ ] ( ) ~ ` > # + = | { } !
    return re.sub(r'\\([._*\[\]()~`>#+=|{}!-])', r'\1', text)

def convert_to_whatsapp_formatting(text):
    """Convert Telegram formatting to WhatsApp formatting"""
    if not text:
        return text
    
    text = clean_whatsapp_text(text)
    
    # Replace formatting while preserving links
    replacements = [
        (r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2'),  # Convert links [text](url) to text url
        (r'<b>(.*?)</b>', r'*\1*'),              # bold
        (r'<strong>(.*?)</strong>', r'*\1*'),
        (r'<i>(.*?)</i>', r'_\1_'),              # italic
        (r'<em>(.*?)</em>', r'_\1_'),
        (r'<u>(.*?)</u>', r'~\1~'),              # underline
        (r'<s>(.*?)</s>', r'~\1~'),              # strikethrough
        (r'<code>(.*?)</code>', r'```\1```'),
        (r'<pre>(.*?)</pre>', r'```\1```')
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    
    return text

async def send_to_destination(context, message):
    """Send exact copy to destination channel (no forwarding)"""
    try:
        if message.text:
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=message.text_markdown_v2 or message.text,
                parse_mode='MarkdownV2',
                disable_web_page_preview=True
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

async def send_to_whatsapp(content, is_media=False, media_url=None, media_type=None):
    """Send message to both WhatsApp account and group"""
    try:
        # Send to WhatsApp account
        account_payload = {
            "token": WHATSAPP_API_TOKEN,
            "to": WHATSAPP_NUMBER,
        }
        
        # Send to WhatsApp group
        group_payload = {
            "token": WHATSAPP_API_TOKEN,
            "to": WHATSAPP_GROUP_ID,
        }
        
        if is_media:
            account_payload.update({
                media_type: media_url,
                "caption": content
            })
            group_payload.update({
                media_type: media_url,
                "caption": content
            })
            
            endpoint = f"messages/{media_type}"
        else:
            account_payload["body"] = content
            group_payload["body"] = content
            endpoint = "messages/chat"
        
        # Send to account
        requests.post(f"{ULTRA_MSG_BASE_URL}/{endpoint}", data=account_payload)
        
        # Send to group (with slight delay to avoid rate limiting)
        await asyncio.sleep(1)
        requests.post(f"{ULTRA_MSG_BASE_URL}/{endpoint}", data=group_payload)
        
        logger.info(f"Content sent to WhatsApp {'group and account' if WHATSAPP_GROUP_ID else 'account'}")
    except Exception as e:
        logger.error(f"Error sending to WhatsApp: {str(e)}")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # 1. Send exact copy to destination Telegram channel
            await send_to_destination(context, message)
            
            # 2. Prepare and send to WhatsApp
            whatsapp_content = ""
            if message.text:
                whatsapp_content = convert_to_whatsapp_formatting(message.text_markdown_v2 or message.text)
                await send_to_whatsapp(whatsapp_content)
            elif message.caption:
                whatsapp_content = convert_to_whatsapp_formatting(message.caption_markdown_v2 or message.caption)
            
            if message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                await send_to_whatsapp(
                    whatsapp_content,
                    is_media=True,
                    media_url=file.file_path,
                    media_type="image"
                )
            elif message.video:
                file = await message.video.get_file()
                await send_to_whatsapp(
                    whatsapp_content,
                    is_media=True,
                    media_url=file.file_path,
                    media_type="video"
                )

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
        logger.error("Another bot instance is already running")
        exit(1)
    
    os.environ["_BOT_RUNNING"] = "1"
    
    try:
        # Start bot thread
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Start Flask
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["_BOT_RUNNING"] = "0"
