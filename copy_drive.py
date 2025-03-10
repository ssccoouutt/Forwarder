import os
import logging
import re
import base64
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive']
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # From Railway environment
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')  # Base64 encoded credentials
CLIENT_SECRET_FILE = 'credentials.json'  # Will be created from environment variable
TOKEN_FILE = 'token.json'  # Will be stored in Railway's ephemeral storage

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
flow = None
progress_data = defaultdict(dict)

FILE_TYPES = {
    'application/pdf': 'PDF',
    'application/vnd.google-apps.document': 'Document',
    'application/vnd.google-apps.spreadsheet': 'Spreadsheet',
    'image/': 'Image',
    'video/': 'Video',
    'audio/': 'Audio',
    'text/': 'Text',
    'application/zip': 'Archive',
    'application/vnd.google-apps.folder': 'Folder'
}

# Create credentials.json from environment variable
if GOOGLE_CREDENTIALS and not os.path.exists(CLIENT_SECRET_FILE):
    try:
        with open(CLIENT_SECRET_FILE, 'w') as f:
            f.write(base64.b64decode(GOOGLE_CREDENTIALS).decode())
    except Exception as e:
        logger.error(f"Failed to create credentials.json: {e}")
        raise

def authorize_google_drive():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    return creds

def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    while size_bytes >= 1024 and unit_index < len(units)-1:
        size_bytes /= 1024
        unit_index += 1
    return f"{size_bytes:.2f} {units[unit_index]}"

async def update_progress(context, chat_id, message_id, current, total, file_types, total_size):
    try:
        progress = (current / total) * 100 if total > 0 else 0
        file_stats = "\n".join([f"{k}: {v}" for k, v in file_types.items() if v > 0])
        size_info = f"📦 Total Size: {format_size(total_size)}"
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📁 Copy Progress: {progress:.1f}%\n{size_info}\n\n📊 File Statistics:\n{file_stats}"
        )
    except Exception as e:
        logger.error(f"Progress update error: {e}")

def categorize_file(mime_type):
    for key, category in FILE_TYPES.items():
        if mime_type.startswith(key):
            return category
    return 'Other'

async def copy_folder(service, folder_id, parent_id, chat_id, context, progress_message):
    try:
        folder = service.files().get(fileId=folder_id, fields='name,mimeType').execute()
        if folder['mimeType'] != 'application/vnd.google-apps.folder':
            return None

        new_folder = service.files().create(body={
            'name': folder['name'],
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id else []
        }, fields='id').execute()

        page_token = None
        while True:
            results = service.files().list(
                q=f"'{folder_id}' in parents",
                fields="nextPageToken, files(id,name,mimeType,size)",
                pageToken=page_token
            ).execute()
            
            items = results.get('files', [])
            for item in items:
                progress_data[chat_id]['processed'] += 1
                current = progress_data[chat_id]['processed']
                total = progress_data[chat_id]['total']
                
                if current % max(1, total//20) == 0 or current == total:
                    await update_progress(
                        context,
                        chat_id,
                        progress_message.message_id,
                        current,
                        total,
                        progress_data[chat_id]['file_types'],
                        progress_data[chat_id]['total_size']
                    )

                category = categorize_file(item['mimeType'])
                progress_data[chat_id]['file_types'][category] += 1

                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    await copy_folder(service, item['id'], new_folder['id'], 
                                    chat_id, context, progress_message)
                else:
                    service.files().copy(
                        fileId=item['id'],
                        body={'name': item['name'], 'parents': [new_folder['id']]}
                    ).execute()

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return new_folder['id']
    except HttpError as e:
        logger.error(f'Drive API Error: {e}')
        raise

def count_files_and_size(service, folder_id):
    total_files = 0
    total_size = 0
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="nextPageToken, files(id,mimeType,size)",
            pageToken=page_token
        ).execute()
        
        items = results.get('files', [])
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                sub_count, sub_size = count_files_and_size(service, item['id'])
                total_files += sub_count
                total_size += sub_size
            else:
                total_files += 1
                total_size += int(item.get('size', 0))
                
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return total_files, total_size

async def handle_google_drive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_message = update.message.text.replace(" ", "").replace("\n", "")
        folder_id = user_message.split('/folders/')[-1].split('?')[0].split('/')[0]
        chat_id = update.message.chat_id
        
        creds = authorize_google_drive()
        if not creds or not creds.valid:
            await start_authorization(update, context)
            return

        service = build('drive', 'v3', credentials=creds)
        
        progress_msg = await update.message.reply_text("🔍 Analyzing folder contents...")
        total_files, total_size = count_files_and_size(service, folder_id)
        await progress_msg.delete()

        progress_data[chat_id] = {
            'total': total_files,
            'processed': 0,
            'file_types': defaultdict(int),
            'total_size': total_size
        }
        
        progress_msg = await update.message.reply_text("🚀 Starting copy process...")
        new_folder_id = await copy_folder(
            service, folder_id, None, chat_id, context, progress_msg
        )
        
        file_stats = "\n".join(
            [f"{k}: {v}" for k, v in progress_data[chat_id]['file_types'].items() if v > 0]
        )
        size_info = format_size(progress_data[chat_id]['total_size'])
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg.message_id,
            text=f"✅ Copy Complete!\n\n📂 Total Files: {total_files}\n📦 Total Size: {size_info}\n\n📊 File Statistics:\n{file_stats}"
        )
        del progress_data[chat_id]
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Main error: {e}")

async def start_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global flow
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    await update.message.reply_text(
        f"🔑 Authorization required!\n\n"
        f"Please visit this link to authorize:\n{auth_url}\n\n"
        "After authorization, send the code you receive back here."
    )

async def handle_authorization_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.replace(" ", "").replace("\n", "")
    global flow
    if flow:
        try:
            flow.fetch_token(code=code)
            with open(TOKEN_FILE, 'w') as token_file:
                token_file.write(flow.credentials.to_json())
            await update.message.reply_text("✅ Authorization successful! You can now send folder links.")
        except Exception as e:
            await update.message.reply_text("❌ Authorization failed. Please try again.")
            logger.error(f"Auth error: {e}")
    else:
        await update.message.reply_text("⚠️ No active authorization session. Send a folder link first.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    cleaned_msg = user_message.replace(" ", "").replace("\n", "")
    
    if re.match(r'^\d+/[\w-]+$', cleaned_msg):
        await handle_authorization_code(update, context)
        return
    
    if 'drive.google.com' in cleaned_msg and '/folders/' in cleaned_msg:
        await handle_google_drive_link(update, context)
    else:
        await update.message.reply_text("⚠️ Please send a valid Google Drive folder link.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    welcome_message = (
        f"<b>Hi {user.first_name}, Welcome to Copy Drive bot!</b>\n\n"
        "<blockquote>"
        "I can upload a Google Drive Folder to your Google Drive. "
        "Just send me a Google Drive Folder Link and I'm ready!"
        "</blockquote>"
    )
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='HTML'
    )

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()