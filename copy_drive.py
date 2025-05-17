import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import logging
import threading
import re
import os
from datetime import datetime, timedelta
import time
from queue import Queue

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "7346090805:AAHUtCp7o7Kd2Ae9ybdJuzb7lRiHl7vyrn8"
DESTINATION_CHANNEL = "1287988079"  # Your private channel ID

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

# Message queue and scheduler
message_queue = Queue()
scheduled_messages = []
next_send_time = None

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
    
    # Remove ALL Telegram escape characters
    text = re.sub(r'\\([^a-zA-Z0-9])', r'\1', text)
    
    # Convert formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)  # bold
    text = re.sub(r'__(.*?)__', r'_\1_', text)      # italic
    text = re.sub(r'~~(.*?)~~', r'~\1~', text)      # strikethrough
    text = re.sub(r'`(.*?)`', r'```\1```', text)    # code
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

async def send_to_destination(context, message):
    """Send to Telegram channel"""
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
        logger.error(f"Error sending to Telegram: {str(e)}")

async def send_to_whatsapp(message):
    """Send message to WhatsApp account and all groups"""
    try:
        # Prepare content
        whatsapp_text = ""
        if message.text:
            whatsapp_text = clean_whatsapp_text(message.text_markdown_v2 or message.text)
        elif message.caption:
            whatsapp_text = clean_whatsapp_text(message.caption_markdown_v2 or message.caption)
        
        if not whatsapp_text:
            return
            
        # Send to WhatsApp account and all groups
        targets = [WHATSAPP_NUMBER] + WHATSAPP_GROUPS
        
        if message.text:
            for target in targets:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": target,
                    "body": whatsapp_text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/chat", data=payload)
                time.sleep(1)  # Rate limiting
        
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            for target in targets:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": target,
                    "image": file.file_path,
                    "caption": whatsapp_text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/image", data=payload)
                time.sleep(1)
        
        elif message.video:
            file = await message.video.get_file()
            for target in targets:
                payload = {
                    "token": WHATSAPP_API_TOKEN,
                    "to": target,
                    "video": file.file_path,
                    "caption": whatsapp_text
                }
                requests.post(f"{ULTRA_MSG_BASE_URL}/messages/video", data=payload)
                time.sleep(1)
        
        logger.info("Message sent to WhatsApp")
            
    except Exception as e:
        logger.error(f"Error sending to WhatsApp: {str(e)}")

async def process_queue(context: ContextTypes.DEFAULT_TYPE):
    """Process scheduled messages from the queue"""
    global next_send_time
    
    while not message_queue.empty():
        message = message_queue.get()
        
        # Send to Telegram
        await send_to_destination(context, message)
        
        # Send to WhatsApp
        await send_to_whatsapp(message)
        
        # Update scheduled messages list
        scheduled_messages.remove(message)
        
        # Set next send time (2 hours from now)
        next_send_time = datetime.now() + timedelta(hours=2)
        message_queue.task_done()
        time.sleep(1)  # Small delay between messages

async def scheduler(context: ContextTypes.DEFAULT_TYPE):
    """Check queue periodically and process messages"""
    while True:
        if not message_queue.empty():
            await process_queue(context)
        await asyncio.sleep(60)  # Check every minute

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stats about scheduled messages"""
    try:
        if update.effective_user.id not in [ADMIN_ID]:  # Add your admin ID
            await update.message.reply_text("You are not authorized to use this command.")
            return
            
        stats = []
        stats.append(f"📊 Message Queue Stats")
        stats.append(f"Messages in queue: {message_queue.qsize()}")
        stats.append(f"Scheduled messages: {len(scheduled_messages)}")
        
        if next_send_time:
            time_left = next_send_time - datetime.now()
            stats.append(f"Next send in: {str(time_left).split('.')[0]}")
        else:
            stats.append("No messages scheduled")
        
        await update.message.reply_text("\n".join(stats))
    except Exception as e:
        logger.error(f"Error in stats command: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from admin"""
    try:
        message = update.message
        
        # Add to queue and schedule
        message_queue.put(message)
        scheduled_messages.append(message)
        
        # Set initial send time if queue was empty
        global next_send_time
        if message_queue.qsize() == 1:
            next_send_time = datetime.now() + timedelta(hours=2)
        
        await update.message.reply_text(
            f"✅ Message received and scheduled\n"
            f"Position in queue: {message_queue.qsize()}\n"
            f"Scheduled for: {next_send_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

async def post_init(application: Application) -> None:
    """Initialization"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot initialized")
    
    # Start scheduler
    asyncio.create_task(scheduler(application))

def run_bot():
    """Run the Telegram bot"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # Handlers
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    application.run_polling(
        close_loop=False,
        stop_signals=[],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    # Check if another instance is running
    if os.environ.get("_BOT_RUNNING") == "1":
        logger.error("Another bot instance is already running")
        exit(1)
    
    os.environ["_BOT_RUNNING"] = "1"
    
    try:
        # Start bot in separate thread
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Start Flask server
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=8000, use_reloader=False)
    finally:
        os.environ["_BOT_RUNNING"] = "0"
