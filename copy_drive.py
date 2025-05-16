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
        # Verification challenge
        if request.method == 'GET':
            if request.args.get('token') == ULTRA_MSG["token"]:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400

        # Process messages
        if data.get('event') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').strip()

            if is_youtube_url(text):
                return handle_youtube_request(phone, text)
            else:
                send_message(phone, "📺 Send any YouTube URL to download the video\nExample: https://youtu.be/dQw4w9WgXcQ")
        
        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def is_youtube_url(text):
    return re.match(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+', text)

def handle_youtube_request(phone, url):
    try:
        send_message(phone, "⏳ Downloading video... (May take 2-5 minutes)")
        
        # Download video (best quality under 1GB)
        file_path, title = download_youtube_video(url)
        
        # Send video via WhatsApp
        send_video(phone, file_path, f"🎬 {title}")
        os.remove(file_path)
        
        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        send_message(phone, f"❌ Error: {str(e)}\nTry a different video or check URL")
        return jsonify({"status": "error"}), 500

def download_youtube_video(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'quiet': True,
        'extract_flat': False,
        'max_filesize': 1000000000,  # 1GB limit (adjust as needed)
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path, info['title']

def send_message(phone, text):
    try:
        response = requests.post(
            f"{ULTRA_MSG['base_url']}/messages/chat",
            data={
                'token': ULTRA_MSG['token'],
                'to': phone,
                'body': text
            },
            timeout=15
        )
        logger.info(f"Message sent to {phone}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return None

def send_video(phone, file_path, caption=""):
    try:
        with open(file_path, 'rb') as video_file:
            response = requests.post(
                f"{ULTRA_MSG['base_url']}/messages/video",
                data={
                    'token': ULTRA_MSG['token'],
                    'to': phone,
                    'caption': caption
                },
                files={'video': video_file},
                timeout=300  # 5 minute timeout for large videos
            )
        logger.info(f"Video sent to {phone}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send video: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("🚀 YouTube Downloader Bot Started")
    serve(app, host='0.0.0.0', port=8000)
