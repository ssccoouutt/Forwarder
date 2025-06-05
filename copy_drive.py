import requests
import asyncio
from telegram import Update, MessageEntity
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
    
    # Only handle private messages (not commands)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    
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
