import requests
import asyncio
from telegram import Update, Message, MessageEntity
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import os

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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def copy_message_with_quotes(message: Message, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Copy message exactly with native Telegram quote formatting"""
    try:
        # Handle text messages with quotes
        if message.text:
            entities = message.entities or []
            quote_entities = [e for e in entities if e.type == MessageEntity.BLOCKQUOTE]
            
            if quote_entities:
                # Reconstruct message with native quote formatting
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message.text,
                    entities=entities,
                    disable_web_page_preview=True
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message.text,
                    disable_web_page_preview=True
                )
        
        # Handle media with captions
        elif message.caption:
            entities = message.caption_entities or []
            quote_entities = [e for e in entities if e.type == MessageEntity.BLOCKQUOTE]
            
            if message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                if quote_entities:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=file.file_id,
                        caption=message.caption,
                        caption_entities=entities
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=file.file_id,
                        caption=message.caption
                    )
            
            elif message.video:
                file = await message.video.get_file()
                if quote_entities:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=file.file_id,
                        caption=message.caption,
                        caption_entities=entities
                    )
                else:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=file.file_id,
                        caption=message.caption
                    )
        
        # Handle media without captions
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(chat_id=chat_id, photo=file.file_id)
        
        elif message.video:
            file = await message.video.get_file()
            await context.bot.send_video(chat_id=chat_id, video=file.file_id)
            
    except Exception as e:
        logger.error(f"Error copying message: {str(e)}")

def clean_whatsapp_text(text):
    """Convert Telegram formatting to WhatsApp formatting"""
    if not text:
        return text
    
    # Remove Telegram's native quote formatting (BLOCKQUOTE entities)
    # WhatsApp doesn't support quote formatting
    return text

async def send_to_whatsapp(message: Message):
    """Send message to WhatsApp account and group"""
    try:
        content = message.text or message.caption
        if not content:
            return
            
        cleaned_content = clean_whatsapp_text(content)
        base_payload = {
            "token": WHATSAPP_API_TOKEN,
            "body": cleaned_content
        }
        
        # Send to both destinations
        for to in [WHATSAPP_NUMBER, WHATSAPP_GROUP_ID]:
            payload = {**base_payload, "to": to}
            
            if message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                payload["image"] = file.file_path
                if message.caption:
                    payload["caption"] = cleaned_content
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
            
            elif message.video:
                file = await message.video.get_file()
                payload["video"] = file.file_path
                if message.caption:
                    payload["caption"] = cleaned_content
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
            
            else:
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
        
        logger.info("Message sent to WhatsApp")
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.chat.username == SOURCE_CHANNEL.strip('@'):
        message = update.channel_post
        logger.info(f"Processing message ID: {message.message_id}")
        
        # 1. Send perfect copy to Telegram destination (with native quotes)
        await copy_message_with_quotes(message, DESTINATION_CHANNEL, context)
        
        # 2. Send to WhatsApp
        await send_to_whatsapp(message)

async def post_init(application: Application):
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot initialized")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling(
        close_loop=False,
        stop_signals=[],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    if os.environ.get("_BOT_RUNNING") == "1":
        logger.error("Bot already running")
        exit(1)
    
    os.environ["_BOT_RUNNING"] = "1"
    
    try:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["_BOT_RUNNING"] = "0"
