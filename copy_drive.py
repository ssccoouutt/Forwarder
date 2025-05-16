import requests
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters
from flask import Flask, jsonify
import logging

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

# Initialize Telegram Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def forward_message(update: Update, context):
    try:
        if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
            message = update.channel_post
            
            # Forward to Telegram
            await bot.forward_message(
                chat_id=DESTINATION_CHANNEL,
                from_chat_id=SOURCE_CHANNEL,
                message_id=message.message_id
            )
            
            # Send to WhatsApp
            if message.text:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "body": message.text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
            
            elif message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "image": file.file_path,
                    "caption": message.caption or ""
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
            
            elif message.video:
                file = await message.video.get_file()
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": WHATSAPP_NUMBER,
                    "video": file.file_path,
                    "caption": message.caption or ""
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)

    except Exception as e:
        logging.error(f"Error: {str(e)}")

def run_bot():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, forward_message))
    application.run_polling()

if __name__ == '__main__':
    from threading import Thread
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8000)
