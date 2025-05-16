from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import tempfile
import os
import re
from yt_dlp import YoutubeDL

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UltraMSG Configuration
ULTRA_MSG = {
    "token": "j0253a3npbpb7ikw",
    "instance_id": "instance116714",
    "base_url": "https://api.ultramsg.com/instance116714"
}

@app.route('/')
def health_check():
    return jsonify({"status": "ready", "service": "YouTube Downloader"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. First log the complete incoming request
        logger.info(f"\n{'='*50}\nINCOMING REQUEST:\n"
                   f"Method: {request.method}\n"
                   f"Headers: {dict(request.headers)}\n"
                   f"Args: {request.args}\n"
                   f"JSON: {request.json}\n"
                   f"{'='*50}")

        # 2. Handle verification
        if request.method == 'GET':
            if request.args.get('token') == ULTRA_MSG["token"]:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        # 3. Process messages
        data = request.json
        if not data:
            logger.error("No data received")
            return jsonify({"error": "No data"}), 400

        if data.get('event') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').strip()

            logger.info(f"Processing message from {phone}: {text}")

            if is_youtube_url(text):
                return handle_youtube_request(phone, text)
            else:
                send_message(phone, "📺 Send any YouTube URL to download video\nExample: https://youtu.be/dQw4w9WgXcQ")
        
        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def is_youtube_url(text):
    return re.match(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+', text)

def handle_youtube_request(phone, url):
    try:
        send_message(phone, "⏳ Downloading video... (3-5 minutes for HD)")
        
        # Download video
        file_path, title = download_youtube_video(url)
        file_size = os.path.getsize(file_path)
        logger.info(f"Downloaded: {title} ({file_size/1024/1024:.2f}MB)")
        
        # Send video
        send_video(phone, file_path, f"🎬 {title}")
        os.remove(file_path)
        
        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"DOWNLOAD FAILED: {str(e)}")
        send_message(phone, f"❌ Error: {str(e)}\nTry a different video")
        return jsonify({"status": "error"}), 500

def download_youtube_video(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'quiet': False,  # Show download progress in logs
        'extract_flat': False,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path, info['title']

def send_message(phone, text):
    try:
        logger.info(f"Sending message to {phone}: {text}")
        response = requests.post(
            f"{ULTRA_MSG['base_url']}/messages/chat",
            data={
                'token': ULTRA_MSG['token'],
                'to': phone,
                'body': text
            },
            timeout=15
        )
        logger.info(f"Message API response: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"MESSAGE SEND ERROR: {str(e)}")
        return None

def send_video(phone, file_path, caption=""):
    try:
        logger.info(f"Attempting to send video to {phone}")
        with open(file_path, 'rb') as video_file:
            response = requests.post(
                f"{ULTRA_MSG['base_url']}/messages/video",
                data={
                    'token': ULTRA_MSG['token'],
                    'to': phone,
                    'caption': caption
                },
                files={'video': video_file},
                timeout=300  # 5 minute timeout
            )
        logger.info(f"Video API response: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"VIDEO SEND ERROR: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("""
    ██╗   ██╗██████╗ ████████╗██╗   ██╗██████╗ ███████╗
    ╚██╗ ██╔╝██╔══██╗╚══██╔══╝██║   ██║██╔══██╗██╔════╝
     ╚████╔╝ ██████╔╝   ██║   ██║   ██║██████╔╝█████╗  
      ╚██╔╝  ██╔═══╝    ██║   ██║   ██║██╔══██╗██╔══╝  
       ██║   ██║        ██║   ╚██████╔╝██████╔╝███████╗
       ╚═╝   ╚═╝        ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝
    WhatsApp YouTube Downloader Service
    """)
    serve(app, host='0.0.0.0', port=8000)
