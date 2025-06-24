import requests
import asyncio
from telegram import Update, MessageEntity
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from flask import Flask, jsonify
import logging
import threading
import re
import os
import time
import heapq
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "7346090805:AAEoJYmSE1reQ1fvkfd7QiiAgTyvrrEpnXQ"
DESTINATION_CHANNEL = "-1001287988079"  # Your private channel

# WhatsApp Configuration
WHATSAPP_API_TOKEN = "uo7ny4ky1m9ol4md"
WHATSAPP_INSTANCE_ID = "instance124468"
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

# Scheduler configuration
QUEUE_LOCK = threading.Lock()
MESSAGE_QUEUE = []
NEXT_SEND_TIME = time.time()
DELAY_HOURS = 4

def adjust_entity_offsets(text, entities):
    """Adjust entity offsets to account for multi-code-point characters"""
    if not entities:
        return entities
    
    # Create a mapping of UTF-16 code unit positions to character positions
    char_pos = 0
    utf16_pos = 0
    pos_map = {}
    
    for char in text:
        pos_map[utf16_pos] = char_pos
        utf16_pos += len(char.encode('utf-16-le')) // 2
        char_pos += 1
    
    # Adjust each entity's offset and length
    adjusted_entities = []
    for entity in entities:
        start = pos_map.get(entity.offset, entity.offset)
        end = pos_map.get(entity.offset + entity.length, entity.offset + entity.length)
        
        # Create new entity with adjusted positions
        new_entity = MessageEntity(
            type=entity.type,
            offset=start,
            length=end - start,
            url=entity.url,
            user=entity.user,
            language=entity.language,
            custom_emoji_id=entity.custom_emoji_id
        )
        adjusted_entities.append(new_entity)
    
    return adjusted_entities

def filter_entities(entities):
    """Filter to only supported formatting entities"""
    allowed_types = {
        MessageEntity.BOLD,
        MessageEntity.ITALIC,
        MessageEntity.CODE,
        MessageEntity.PRE,
        MessageEntity.UNDERLINE,
        MessageEntity.STRIKETHROUGH,
        MessageEntity.TEXT_LINK,
        MessageEntity.SPOILER,
        "blockquote"
    }
    return [e for e in entities if getattr(e, 'type', None) in allowed_types] if entities else []

def apply_telegram_formatting(text, entities):
    """Apply all formatting with proper nesting for Telegram"""
    if not text:
        return text
    
    # Convert to list for character-level manipulation
    chars = list(text)
    text_length = len(chars)
    
    # Sort entities by offset (reversed for proper insertion)
    sorted_entities = sorted(entities or [], key=lambda e: -e.offset)
    
    # Entity processing map
    entity_tags = {
        MessageEntity.BOLD: ('<b>', '</b>'),
        MessageEntity.ITALIC: ('<i>', '</i>'),
        MessageEntity.UNDERLINE: ('<u>', '</u>'),
        MessageEntity.STRIKETHROUGH: ('<s>', '</s>'),
        MessageEntity.SPOILER: ('<tg-spoiler>', '</tg-spoiler>'),
        MessageEntity.CODE: ('<code>', '</code>'),
        MessageEntity.PRE: ('<pre>', '</pre>'),
        MessageEntity.TEXT_LINK: (lambda e: f'<a href="{e.url}">', '</a>'),
        "blockquote": ('<blockquote>', '</blockquote>')
    }
    
    for entity in sorted_entities:
        entity_type = getattr(entity, 'type', None)
        if entity_type not in entity_tags:
            continue
            
        start_tag, end_tag = entity_tags[entity_type]
        if callable(start_tag):
            start_tag = start_tag(entity)
            
        start = entity.offset
        end = start + entity.length
        
        # Validate positions
        if start >= text_length or end > text_length:
            continue
            
        # Apply formatting
        before = ''.join(chars[:start])
        content = ''.join(chars[start:end])
        after = ''.join(chars[end:])
        
        # Special handling for blockquotes to prevent nesting issues
        if entity_type == "blockquote":
            content = content.replace('<b>', '').replace('</b>', '')
            content = content.replace('<i>', '').replace('</i>', '')
        
        chars = list(before + start_tag + content + end_tag + after)
        text_length = len(chars)
    
    # Handle manual blockquotes (lines starting with >)
    formatted_text = ''.join(chars)
    if ">" in formatted_text:
        formatted_text = formatted_text.replace("&gt;", ">")
        lines = formatted_text.split('\n')
        formatted_lines = []
        in_blockquote = False
        
        for line in lines:
            if line.startswith('>'):
                if not in_blockquote:
                    formatted_lines.append('<blockquote>')
                    in_blockquote = True
                formatted_lines.append(line[1:].strip())
            else:
                if in_blockquote:
                    formatted_lines.append('</blockquote>')
                    in_blockquote = False
                formatted_lines.append(line)
        
        if in_blockquote:
            formatted_lines.append('</blockquote>')
        
        formatted_text = '\n'.join(formatted_lines)
    
    # Final HTML escaping (except for our tags)
    formatted_text = formatted_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Re-insert our HTML tags
    html_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a', 'tg-spoiler', 'blockquote']
    for tag in html_tags:
        formatted_text = formatted_text.replace(f'&lt;{tag}&gt;', f'<{tag}>').replace(f'&lt;/{tag}&gt;', f'</{tag}>')
    
    return formatted_text

def clean_whatsapp_text(text, entities=None):
    """Convert Telegram formatting to WhatsApp formatting with proper handling"""
    if not text:
        return text
    
    # If we have entities, use them for more accurate formatting
    if entities:
        entities = adjust_entity_offsets(text, entities)
        
        # Convert to list for character-level manipulation
        text_list = list(text)
        
        # Process each entity type separately
        entity_types = {
            MessageEntity.BOLD: ('*', '*'),
            MessageEntity.ITALIC: ('_', '_'),
            MessageEntity.STRIKETHROUGH: ('~', '~'),
            MessageEntity.CODE: ('```', '```'),
            MessageEntity.PRE: ('```\n', '\n```')
        }
        
        # Sort entities by offset in reverse order to avoid position shifting
        for entity in sorted(entities, key=lambda e: -e.offset):
            if entity.type in entity_types:
                prefix, suffix = entity_types[entity.type]
                start = entity.offset
                end = start + entity.length
                
                # Extract the content
                content = text[start:end]
                
                # Special handling for PRE to maintain newlines
                if entity.type == MessageEntity.PRE:
                    replacement = f"{prefix}{content}{suffix}"
                else:
                    # For other types, process line by line
                    lines = content.split('\n')
                    wrapped_lines = []
                    for line in lines:
                        if line.strip():  # Only wrap non-empty lines
                            wrapped_lines.append(f"{prefix}{line.strip()}{suffix}")
                        else:  # Preserve empty lines
                            wrapped_lines.append('')
                    replacement = '\n'.join(wrapped_lines)
                
                # Replace the original section
                text_list[start:end] = replacement
        
        text = ''.join(text_list)
    else:
        # Fallback to regex processing if no entities available
        text = re.sub(r'\\([^a-zA-Z0-9])', r'\1', text)  # Remove escapes
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)   # bold
        text = re.sub(r'__(.*?)__', r'_\1_', text)       # italic
        text = re.sub(r'~~(.*?)~~', r'~\1~', text)       # strikethrough
        text = re.sub(r'`(.*?)`', r'```\1```', text)     # code
    
    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

async def send_to_destination(context, message):
    """Send to private Telegram channel with proper formatting"""
    try:
        # Prepare content
        telegram_text = ""
        entities = None
        
        if message.text:
            telegram_text = message.text
            entities = message.entities
        elif message.caption:
            telegram_text = message.caption
            entities = message.caption_entities
        
        # Apply Telegram formatting
        if telegram_text:
            filtered_entities = filter_entities(entities)
            adjusted_entities = adjust_entity_offsets(telegram_text, filtered_entities)
            formatted_text = apply_telegram_formatting(telegram_text, adjusted_entities)
        else:
            formatted_text = None

        # Send based on message type
        if message.text:
            await context.bot.send_message(
                chat_id=DESTINATION_CHANNEL,
                text=formatted_text or message.text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            await context.bot.send_photo(
                chat_id=DESTINATION_CHANNEL,
                photo=file.file_id,
                caption=formatted_text if message.caption else None,
                parse_mode=ParseMode.HTML
            )
        elif message.video:
            file = await message.video.get_file()
            await context.bot.send_video(
                chat_id=DESTINATION_CHANNEL,
                video=file.file_id,
                caption=formatted_text if message.caption else None,
                parse_mode=ParseMode.HTML
            )
        logger.info("Message sent to Telegram channel")
    except Exception as e:
        logger.error(f"Telegram send error: {str(e)}")

async def send_to_whatsapp(message):
    """Send to all WhatsApp targets"""
    try:
        # Prepare content
        whatsapp_text = ""
        entities = None
        
        if message.text:
            whatsapp_text = message.text
            entities = message.entities
        elif message.caption:
            whatsapp_text = message.caption
            entities = message.caption_entities
        
        if not whatsapp_text:
            return
            
        # Clean and format the text
        formatted_text = clean_whatsapp_text(whatsapp_text, entities)
        
        # Send to all targets (account + groups)
        targets = [WHATSAPP_NUMBER] + WHATSAPP_GROUPS
        
        if message.text:
            for target in targets:
                requests.post(
                    f"{ULTRA_MSG_BASE_URL}/messages/chat",
                    data={
                        "token": WHATSAPP_API_TOKEN,
                        "to": target,
                        "body": formatted_text
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
                        "caption": formatted_text
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
                        "caption": formatted_text
                    }
                )
        
        logger.info(f"Message sent to {len(targets)} WhatsApp targets")
            
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")

def get_message_preview(message):
    """Get first 30 characters of message text for identification"""
    if message.text:
        return message.text[:30] + ("..." if len(message.text) > 30 else "")
    elif message.caption:
        return message.caption[:30] + ("..." if len(message.caption) > 30 else "")
    return "Media message"

def schedule_message(update, context, message):
    """Add message to scheduling queue with delay"""
    global NEXT_SEND_TIME
    
    with QUEUE_LOCK:
        # Calculate send time (4 hours after last scheduled message)
        send_time = NEXT_SEND_TIME if NEXT_SEND_TIME > time.time() else time.time()
        if MESSAGE_QUEUE:
            send_time = max(send_time, heapq.nlargest(1, MESSAGE_QUEUE)[0][0])
        send_time += DELAY_HOURS * 3600
        NEXT_SEND_TIME = send_time
        
        # Create message data package
        message_data = {
            'update': update,
            'context': context,
            'message': message,
            'preview': get_message_preview(message),
            'send_time': send_time
        }
        
        # Add to priority queue (min-heap by send time)
        heapq.heappush(MESSAGE_QUEUE, (send_time, message_data))
        logger.info(f"Scheduled message for {datetime.fromtimestamp(send_time)}")
        
        # Notify user
        send_time_str = datetime.fromtimestamp(send_time).strftime("%Y-%m-%d %H:%M:%S")
        asyncio.run_coroutine_threadsafe(
            context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"📅 Post scheduled for delivery at {send_time_str}"
            ),
            context.bot._loop
        )

async def process_queue():
    """Process scheduled messages from the queue"""
    while True:
        now = time.time()
        with QUEUE_LOCK:
            # Process all messages that are due
            while MESSAGE_QUEUE and MESSAGE_QUEUE[0][0] <= now:
                send_time, message_data = heapq.heappop(MESSAGE_QUEUE)
                message = message_data['message']
                context = message_data['context']
                
                # Send to Telegram and WhatsApp
                await send_to_destination(context, message)
                await send_to_whatsapp(message)
                logger.info(f"Sent scheduled message originally received at {message.date}")
        
        # Wait before checking again
        await asyncio.sleep(30)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message:
            return
            
        # Only process messages from private chats
        if message.chat.type != "private":
            logger.info(f"Ignoring non-private message from chat type: {message.chat.type}")
            return
            
        logger.info(f"New private message received from {message.from_user.id}")
        
        # Check if message is forwarded
        if message.forward_from or message.forward_from_chat:
            # Schedule forwarded messages with delay
            schedule_message(update, context, message)
        else:
            # Direct messages - send immediately
            await send_to_destination(context, message)
            await send_to_whatsapp(message)

    except Exception as e:
        logger.error(f"Processing error: {str(e)}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show scheduled posts in the queue"""
    try:
        with QUEUE_LOCK:
            if not MESSAGE_QUEUE:
                await update.message.reply_text("📭 No scheduled posts in queue")
                return
                
            response = "⏱ Scheduled Posts:\n\n"
            for idx, (send_time, msg_data) in enumerate(heapq.nsmallest(10, MESSAGE_QUEUE), 1):
                send_time_str = datetime.fromtimestamp(send_time).strftime("%Y-%m-%d %H:%M:%S")
                response += f"{idx}. 🕒 {send_time_str}\n   📝 {msg_data['preview']}\n\n"
                
            await update.message.reply_text(response)
            
    except Exception as e:
        logger.error(f"/check command error: {str(e)}")
        await update.message.reply_text("❌ Error retrieving schedule")

async def post_init(application: Application) -> None:
    """Initial setup"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    # Start queue processing task
    asyncio.create_task(process_queue())
    logger.info("Bot initialized and ready")

def run_bot():
    """Run the Telegram bot"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # Add handlers
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("check", check_command))
    
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
