from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import os
import validators
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GreenAPI Configuration
INSTANCE_ID = "7105242995"
API_TOKEN = "d8822c5bc02d4b00b72455cc64abd11ad672072fbe5d4bf9a2"
BASE_API_URL = "https://7105.api.greenapi.com"
BASE_MEDIA_URL = "https://7105.media.greenapi.com"
AUTHORIZED_NUMBER = "923190779215"  # Only respond to this number
BOT_NUMBER = "923247220362"  # Your bot's number

# Temporary directory for downloads
TEMP_DIR = "temp_downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.route('/')
def health_check():
    """Endpoint for Koyeb health checks"""
    return jsonify({"status": "ready", "service": "WhatsApp Media Bot"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        logger.info(f"\n{'='*50}\nIncoming request: {request.method}")
        
        # Verification challenge (if needed)
        if request.method == 'GET':
            return jsonify({"status": "active"}), 200

        data = request.json
        if not data:
            logger.error("No data received")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        logger.info(f"Request data: {data}")

        # Process incoming messages
        if data.get('typeWebhook') == 'incomingMessageReceived':
            message_data = data.get('messageData', {})
            sender_data = data.get('senderData', {})
            
            sender_number = sender_data.get('sender', '').replace('@c.us', '')
            message_text = message_data.get('textMessageData', {}).get('textMessage', '').strip()
            
            # Only respond to authorized number
            if sender_number != AUTHORIZED_NUMBER:
                logger.info(f"Ignoring message from unauthorized number: {sender_number}")
                return jsonify({'status': 'ignored'})
            
            logger.info(f"Processing message from {sender_number}: {message_text}")
            
            # Check if message is a valid URL
            if validators.url(message_text):
                # Download and send back the media
                process_media_url(message_text, sender_number)
            else:
                send_message(sender_number, "Please send a direct download link to an image or video file.")
            
        return jsonify({'status': 'processed'})
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_media_url(url, recipient_number, retries=3):
    """Download media from URL and send back to user"""
    try:
        # Check if the URL points to a media file
        if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.webm']):
            send_message(recipient_number, "The link must point directly to an image (jpg, png, gif) or video (mp4, mov) file.")
            return
        
        send_message(recipient_number, "🔍 Downloading your media file...")
        
        # Download the file
        filename = os.path.join(TEMP_DIR, url.split('/')[-1].split('?')[0])
        
        for attempt in range(retries):
            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Successfully downloaded file: {filename}")
                break
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2)
        
        # Determine media type
        if filename.lower().endswith(('.mp4', '.mov', '.webm')):
            media_type = 'video'
            mime_type = 'video/mp4'
        else:
            media_type = 'image'
            mime_type = 'image/jpeg'
        
        # Send the file back
        send_file(recipient_number, filename, media_type, mime_type)
        
        # Clean up
        os.remove(filename)
        
    except Exception as e:
        logger.error(f"Error processing media URL: {str(e)}")
        send_message(recipient_number, "❌ Failed to process the media file. Please check the link and try again.")

def send_message(recipient_number, text, retries=3):
    """Send WhatsApp message"""
    chat_id = f"{recipient_number}@c.us"
    url = f"{BASE_API_URL}/waInstance{INSTANCE_ID}/sendMessage/{API_TOKEN}"
    
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                json={
                    'chatId': chat_id,
                    'message': text
                },
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Message sent to {recipient_number}")
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to send message (attempt {attempt + 1}): {str(e)}")
            if attempt == retries - 1:
                raise
            time.sleep(2)

def send_file(recipient_number, file_path, media_type, mime_type, caption="Here's your media file", retries=3):
    """Send media file through WhatsApp"""
    chat_id = f"{recipient_number}@c.us"
    filename = os.path.basename(file_path)
    url = f"{BASE_MEDIA_URL}/waInstance{INSTANCE_ID}/sendFileByUpload/{API_TOKEN}"
    
    for attempt in range(retries):
        try:
            with open(file_path, 'rb') as file:
                files = {
                    'file': (filename, file, mime_type)
                }
                payload = {
                    'chatId': chat_id,
                    'caption': caption,
                    'fileName': filename
                }
                
                response = requests.post(url, data=payload, files=files, timeout=30)
                response.raise_for_status()
                logger.info(f"{media_type.capitalize()} sent to {recipient_number}")
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to send {media_type} (attempt {attempt + 1}): {str(e)}")
            if attempt == retries - 1:
                raise
            time.sleep(2)

if __name__ == '__main__':
    logger.info("Starting WhatsApp Media Bot...")
    serve(app, host='0.0.0.0', port=8000)
