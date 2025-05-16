from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import tempfile
import os
import re
import time
import subprocess
from yt_dlp import YoutubeDL

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"
COOKIES_FILE = "cookies.txt"  # Path to cookies file
MAX_RETRIES = 3

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
        send_message(phone, "⏳ Downloading video... (this may take a few minutes)")
        
        # Create a temporary directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = download_youtube_video(url, temp_dir)
            if not file_path or not os.path.exists(file_path):
                raise Exception("Failed to download video or file not found")

            file_size = os.path.getsize(file_path)
            logger.info(f"Downloaded: {file_path} ({file_size/1024/1024:.2f}MB)")
            
            # Check if file needs compression (WhatsApp limit is ~16MB)
            if file_size > 15 * 1024 * 1024:  # 15MB
                send_message(phone, "📦 File is large, compressing...")
                compressed_path = os.path.join(temp_dir, "compressed.mp4")
                if compress_video(file_path, compressed_path):
                    file_path = compressed_path
                    logger.info(f"Compressed to: {os.path.getsize(file_path)/1024/1024:.2f}MB")
                else:
                    logger.warning("Compression failed, sending original")

            send_video(phone, file_path, "🎬 Your YouTube Video")
        
        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"DOWNLOAD FAILED: {str(e)}")
        error_msg = "❌ Failed to download video. YouTube may be blocking the download. Try again later."
        if "HTTP Error 403" in str(e):
            error_msg = "❌ YouTube blocked this download. Try a different video."
        send_message(phone, error_msg)
        return jsonify({"status": "error"}), 500

def download_youtube_video(url, temp_dir):
    ydl_opts = {
        'format': 'best[height<=720]',  # Limit to 720p to reduce size
        'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),  # Use video ID as filename
        'quiet': False,
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'ignoreerrors': True,
        'retries': MAX_RETRIES,
        'socket_timeout': 30,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash', 'translated_subs']
            }
        },
        'postprocessor_args': {
            'ffmpeg': ['-b:v', '1500k']  # Set target video bitrate
        }
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Failed to extract video info")
                
            file_path = ydl.prepare_filename(info)
            
            # Ensure the file exists and has content
            if not os.path.exists(file_path):
                raise Exception("Downloaded file not found")
            if os.path.getsize(file_path) == 0:
                raise Exception("Downloaded file is empty")
                
            return file_path
            
    except Exception as e:
        logger.error(f"YT-DLP ERROR: {str(e)}")
        raise Exception(f"YouTube download failed: {str(e)}")

def compress_video(input_path, output_path):
    try:
        command = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-crf', '28',  # Higher CRF = more compression
            '-preset', 'fast',
            '-c:a', 'copy',  # Keep original audio
            output_path
        ]
        subprocess.run(command, check=True, capture_output=True)
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"COMPRESSION ERROR: {str(e)}")
        return False

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
    logger.info("Starting YouTube Downloader Service with improved download logic...")
    serve(app, host='0.0.0.0', port=8000)
