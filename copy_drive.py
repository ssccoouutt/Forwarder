import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import re

# Initialize Flask app for Koyeb health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

# Telegram Configuration (HARDCODED)
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
SOURCE_CHANNEL = "@Source069"
DESTINATION_CHANNEL = "@Destination07"

# UltraMSG Configuration (HARDCODED)
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
    
    # Convert bold: <b>text</b> or **text** to *text*
    text = re.sub(r'<b>(.*?)</b>|\\*\\*(.*?)\\*\\*', lambda m: f"*{m.group(1) or m.group(2)}*", text)
    
    # Convert italic: <i>text</i> or __text__ to _text_
    text = re.sub(r'<i>(.*?)</i>|__(.*?)__', lambda m: f"_{m.group(1) or m.group(2)}_", text)
    
    # Convert underline: <u>text</u> to ~text~
    text = re.sub(r'<u>(.*?)</u>', r'~\1~', text)
    
    # Convert code: <code>text</code> or `text` to ```text```
    text = re.sub(r'<code>(.*?)</code>|`(.*?)`', lambda m: f"```{m.group(1) or m.group(2)}```", text)
    
    # Convert strikethrough: <s>text</s> or ~~text~~ to ~text~
    text = re.sub(r'<s>(.*?)</s>|~~(.*?)~~', lambda m: f"~{m.group(1) or m.group(2)}~", text)
    
    return text

async def send_copy_to_destination(context, message):
    """Send a copy of the message to destination channel (not forwarded)"""
    try:
        if message.text:
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=message.text,
                parse_mode='HTML'
            )
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(
                chat_id=DESTINATION_CHANNEL,
                photo=file.file_id,
                caption=message.caption or "",
                parse_mode='HTML'
            )
        elif message.video:
            file = await message.video.get_file()
            await context.bot.send_video(
                chat_id=DESTINATION_CHANNEL,
                video=file.file_id,
                caption=message.caption or "",
                parse_mode='HTML'
            )
        logger.info("Message copied to destination channel")
    except Exception as e:
        logger.error(f"Error sending copy to destination: {str(e)}")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # Send copy to destination channel (not forwarded)
            await send_copy_to_destination(context, message)
            
            # Send to WhatsApp with formatting conversion
            if message.text:
                whatsapp_text = convert_telegram_to_whatsapp(message.text_html)
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
                whatsapp_caption = convert_telegram_to_whatsapp(message.caption_html if message.caption else "")
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "image": file.file_path,
                    "caption": whatsapp_caption
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
                logger.info("Photo sent to WhatsApp")
            
            elif message.video:
                file = await message.video.get_file()
                whatsapp_caption = convert_telegram_to_whatsapp(message.caption_html if message.caption else "")
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "video": file.file_path,
                    "caption": whatsapp_caption
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
