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
DESTINATION_CHANNEL = "-1001287988079"  # Your private channel

# WhatsApp Configuration
WHATSAPP_API_TOKEN = "j0253a3npbpb7ikw"
WHATSAPP_INSTANCE_ID = "instance116714"
WHATSAPP_NUMBER = "923247220362"  # Your linked number
WHATSAPP_GROUPS = [
    "120363140590753276@g.us",  # Original group
    "120363162260844407@g.us",
    "120363042237526273@g.us", 
    "120363023394033137@g.us",
    "120363161222427319@g.us"
]
ULTRA_MSG_BASE_URL = f"https://api.ultramsg.com/{WHATSAPP_INSTANCE_ID}"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def clean_whatsapp_text(text):
    """Clean text for WhatsApp with enhanced formatting handling"""
    if not text:
        return text
    
    # Remove ALL Telegram escape characters
    text = re.sub(r'\\([^a-zA-Z0-9])', r'\1', text)
    
    # Convert formatting with line-by-line processing
    def format_lines(pattern, wrapper):
        def replacer(match):
            content = match.group(1)
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            return '\n'.join([f'{wrapper}{line}{wrapper}' for line in lines])
        return replacer
    
    # Apply formatting conversions with multiline support
    text = re.sub(r'\*\*(.*?)\*\*', format_lines(r'\*\*(.*?)\*\*', '*'), text, flags=re.DOTALL)
    text = re.sub(r'__(.*?)__', format_lines(r'__(.*?)__', '_'), text, flags=re.DOTALL)
    text = re.sub(r'~~(.*?)~~', format_lines(r'~~(.*?)~~', '~'), text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', format_lines(r'`(.*?)`', '```'), text, flags=re.DOTALL)
    
    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

async def send_to_destination(context, message):
    """Send to private Telegram channel"""
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
        logger.info("Message sent to Telegram channel")
    except Exception as e:
        logger.error(f"Telegram send error: {str(e)}")

async def send_to_whatsapp(message):
    """Send to all WhatsApp targets"""
    try:
        # Prepare content
        whatsapp_text = ""
        if message.text:
            whatsapp_text = clean_whatsapp_text(message.text_markdown_v2 or message.text)
        elif message.caption:
            whatsapp_text = clean_whatsapp_text(message.caption_markdown_v2 or message.caption)
        
        if not whatsapp_text:
            return
            
        # Send to all targets (account + groups)
        targets = [WHATSAPP_NUMBER] + WHATSAPP_GROUPS
        
        if message.text:
            for target in targets:
                requests.post(
                    f"{ULTRA_MSG_BASE_URL}/messages/chat",
                    data={
                        "token": WHATSAPP_API_TOKEN,
                        "to": target,
                        "body": whatsapp_text
                    }
                )
        
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            for target in targets:
                requests.post(
                    f"{ULTRA_MSG_BASE_URL}/messages/image",
                    data={
                        "token": WHATSAPP_API_TOKEN,
                        "to": target,
                        "image": file.file_path,
                        "caption": whatsapp_text
                    }
                )
        
        elif message.video:
            file = await message.video.get_file()
            for target in targets:
                requests.post(
                    f"{ULTRA_MSG_BASE_URL}/messages/video",
                    data={
                        "token": WHATSAPP_API_TOKEN,
                        "to": target,
                        "video": file.file_path,
                        "caption": whatsapp_text
                    }
                )
        
        logger.info(f"Message sent to {len(targets)} WhatsApp targets")
            
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message:
            return
            
        logger.info(f"New message received from {message.from_user.id}")
        
        # 1. Send to Telegram channel
        await send_to_destination(context, message)
        
        # 2. Send to all WhatsApp targets
        await send_to_whatsapp(message)

    except Exception as e:
        logger.error(f"Processing error: {str(e)}")

async def post_init(application: Application) -> None:
    """Initial setup"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot initialized and ready")

def run_bot():
    """Run the Telegram bot"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # Only listen to private messages (direct chats)
    app.add_handler(MessageHandler(filters.CHAT_TYPE.PRIVATE & ~filters.COMMAND, handle_message))
    
    app.run_polling(
        close_loop=False,
        stop_signals=[],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    # Single instance check
    if os.environ.get("BOT_LOCK") == "1":
        logger.error("Bot already running")
        exit(1)
    
    os.environ["BOT_LOCK"] = "1"
    
    try:
        # Start bot thread
        threading.Thread(target=run_bot, daemon=True).start()
        
        # Start Flask
        logger.info("Starting server...")
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["BOT_LOCK"] = "0"
