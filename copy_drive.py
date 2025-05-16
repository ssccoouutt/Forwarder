from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import tempfile
import os
import re
import time
from yt_dlp import YoutubeDL

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"
COOKIES_FILE = "cookies.txt"  # Path to cookies file

@app.route('/')
def health_check():
    return jsonify({"status": "ready", "service": "YouTube Downloader"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        logger.info(f"\n{'='*50}\nINCOMING REQUEST:\nMethod: {request.method}\nHeaders: {dict(request.headers)}\nArgs: {request.args}\nJSON: {request.json}\n{'='*50}")

        if request.method == 'GET':
            if request.args.get('token') == TOKEN:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        data = request.json
        if not data:
            logger.error("No data received")
            return jsonify({"error": "No data"}), 400

        if data.get('event_type') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').strip()

            logger.info(f"Processing message from {phone}: {text}")

            if text.lower() in ['hi', 'hello', 'hey']:
                send_message(phone, "📺 Hello! Send me any YouTube URL to download the video")
                return jsonify({"status": "success"})
                
            elif text.lower() in ['help', 'info']:
                send_message(phone, "ℹ️ Just send me a YouTube URL and I'll download the video for you!\nExample: https://youtu.be/dQw4w9WgXcQ")
                return jsonify({"status": "success"})

            elif is_youtube_url(text):
                return handle_youtube_request(phone, text)
            else:
                send_message(phone, "📺 Please send a valid YouTube URL\nExample: https://youtu.be/dQw4w9WgXcQ")
        
        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def is_youtube_url(text):
    return re.match(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+', text)

def handle_youtube_request(phone, url):
    try:
        send_message(phone, "⏳ Downloading video... (3-5 minutes for HD)")
        
        file_path, title = download_youtube_video(url)
        if not file_path:
            raise Exception("Failed to download video")

        file_size = os.path.getsize(file_path)
        logger.info(f"Downloaded: {title} ({file_size/1024/1024:.2f}MB)")
        
        send_video(phone, file_path, f"🎬 {title}")
        os.remove(file_path)
        
        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"DOWNLOAD FAILED: {str(e)}")
        send_message(phone, f"❌ Error: {str(e)}\nTry a different video or try again later")
        return jsonify({"status": "error"}), 500

def download_youtube_video(url):
    ydl_opts = {
        'format': 'best[filesize<20M]',
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'quiet': False,
        'extract_flat': False,
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'ignoreerrors': True,
        'retries': 3,
        'socket_timeout': 30,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash', 'translated_subs']
            }
        }
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Failed to extract video info")
                
            file_path = ydl.prepare_filename(info)
            return file_path, info['title']
            
    except Exception as e:
        logger.error(f"YT-DLP ERROR: {str(e)}")
        raise Exception("YouTube download failed. The video may be restricted or unavailable")

def send_message(phone, text, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/chat",
                data={'token': TOKEN, 'to': phone, 'body': text},
                timeout=15
            )
            logger.info(f"Message sent to {phone} (attempt {attempt+1}): {response.status_code}")
            return response.json()
        except Exception as e:
            logger.warning(f"Message send failed (attempt {attempt+1}): {str(e)}")
            time.sleep(2)
    logger.error(f"Failed to send message to {phone} after {retries} attempts")
    return None

def send_video(phone, file_path, caption="", retries=3):
    for attempt in range(retries):
        try:
            with open(file_path, 'rb') as video_file:
                response = requests.post(
                    f"{BASE_URL}/messages/video",
                    data={'token': TOKEN, 'to': phone, 'caption': caption},
                    files={'video': video_file},
                    timeout=300
                )
            logger.info(f"Video sent to {phone} (attempt {attempt+1}): {response.status_code}")
            return response.json()
        except Exception as e:
            logger.warning(f"Video send failed (attempt {attempt+1}): {str(e)}")
            time.sleep(5)
    logger.error(f"Failed to send video to {phone} after {retries} attempts")
    return None

if __name__ == '__main__':
    logger.info("Starting YouTube Downloader Service with cookies support...")
    serve(app, host='0.0.0.0', port=8000)
