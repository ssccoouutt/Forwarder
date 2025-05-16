import requests
import asyncio
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading

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
    text = re.sub(r'<b>(.*?)</b>|\\*\\*(.*?)\\*\\*', r'*\1\2*', text)
    
    # Convert italic: <i>text</i> or __text__ to _text_
    text = re.sub(r'<i>(.*?)</i>|__(.*?)__', r'_\1\2_', text)
    
    # Convert code: <code>text</code> or `text` to ```text```
    text = re.sub(r'<code>(.*?)</code>|`(.*?)`', r'```\1\2```', text)
    
    # Convert underline: <u>text</u> to ~text~
    text = re.sub(r'<u>(.*?)</u>', r'~\1~', text)
    
    # Remove other HTML tags
    text = re.sub(r'<.*?>', '', text)
    
    return text

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            logger.info(f"New message received: {message.message_id}")
            
            # Forward original message to Telegram channel
            await context.bot.forward_message(
                chat_id=DESTINATION_CHANNEL,
                from_chat_id=SOURCE_CHANNEL,
                message_id=message.message_id
            )
            logger.info("Message forwarded to Telegram channel")
            
            # Prepare WhatsApp message
            if message.text:
                whatsapp_text = convert_telegram_to_whatsapp(message.text)
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "body": whatsapp_text
                }
                response = requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
                logger.info(f"Text sent to WhatsApp: {response.json()}")
            
            elif message.caption:
                whatsapp_text = convert_telegram_to_whatsapp(message.caption)
                if message.photo:
                    photo = message.photo[-1]
                    file = await photo.get_file()
                    payload = {
                        "token": WHATSAPP_API_TOKEN,
                        "to": WHATSAPP_NUMBER,
                        "image": file.file_path,
                        "caption": whatsapp_text
                    }
                    response = requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
                    logger.info(f"Photo with caption sent to WhatsApp: {response.json()}")
                
                elif message.video:
                    file = await message.video.get_file()
                    payload = {
                        "token": WHATSAPP_API_TOKEN,
                        "to": WHATSAPP_NUMBER,
                        "video": file.file_path,
                        "caption": whatsapp_text
                    }
                    response = requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
                    logger.info(f"Video with caption sent to WhatsApp: {response.json()}")

    except Exception as e:
        logger.error(f"Error in forward_message: {str(e)}")

def run_bot():
    """Run the Telegram bot in its own event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, forward_message))
    
    logger.info("Starting Telegram bot polling...")
    application.run_polling()

if __name__ == '__main__':
    # Start Telegram bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=8000)
