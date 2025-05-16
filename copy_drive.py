from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ULTRA_MSG = {
    "token": "j0253a3npbpb7ikw",
    "instance_id": "instance116714",
    "base_url": "https://api.ultramsg.com/instance116714"
}

GLIF = {
    "app_id": "cm0zceq2a00023f114o6hti7w",
    "tokens": [
        "glif_a4ef6d3aa5d8575ea8448b29e293919a42a6869143fcbfc32f2e4a7dbe53199a",
        "glif_51d216db54438b777c4170cd8913d628ff0af09789ed5dbcbd718fa6c6968bb1",
        "glif_c9dc66b31537b5a423446bbdead5dc2dbd73dc1f4a5c47a9b77328abcbc7b755",
        "glif_f5a55ee6d767b79f2f3af01c276ec53d14475eace7cabf34b22f8e5968f3fef5",
        "glif_c3a7fd4779b59f59c08d17d4a7db46beefa3e9e49a9ebc4921ecaca35c556ab7",
        "glif_b31fdc2c9a7aaac0ec69d5f59bf05ccea0c5786990ef06b79a1d7db8e37ba317"
    ]
}

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. First log the complete request
        logger.info(f"\n{'='*50}\nINCOMING REQUEST:\n"
                   f"Method: {request.method}\n"
                   f"Headers: {dict(request.headers)}\n"
                   f"Args: {request.args}\n"
                   f"Data: {request.data}\n"
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
            return jsonify({"error": "No data"}), 400

        # UltraMSG sends different event types
        if data.get('event') == 'message_received':
            return handle_message(data.get('data', {}))
        
        # Ignore other events (acknowledgements, etc)
        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_message(msg):
    try:
        phone = msg.get('from', '').split('@')[0]
        text = msg.get('body', '').strip().lower()

        if not text:
            return send_message(phone, "Please send a text message")

        # Command processing
        if text in ['hi', 'hello', 'hey']:
            return send_message(phone, "👋 Send me a topic to generate a thumbnail!")
            
        if text in ['help', 'info']:
            return send_message(phone, "ℹ️ Just send me a topic (e.g. 'sunset beach')")

        # Generate thumbnail
        send_message(phone, "🔄 Generating your thumbnail...")
        
        for token in GLIF["tokens"]:
            image_url = generate_thumbnail(text, token)
            if image_url:
                send_image(phone, image_url, f"🎨 Thumbnail for: {text}")
                send_message(phone, f"🔗 Direct URL: {image_url}")
                return jsonify({"status": "success"})

        send_message(phone, "❌ Failed to generate. Please try different keywords.")
        return jsonify({"status": "error"})

    except Exception as e:
        logger.error(f"Message handling failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_message(phone, text):
    try:
        response = requests.post(
            f"{ULTRA_MSG['base_url']}/messages/chat",
            data={
                'token': ULTRA_MSG['token'],
                'to': phone,
                'body': text
            },
            timeout=10
        )
        logger.info(f"Message sent to {phone}")
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return None

def send_image(phone, url, caption):
    try:
        response = requests.post(
            f"{ULTRA_MSG['base_url']}/messages/image",
            data={
                'token': ULTRA_MSG['token'],
                'to': phone,
                'image': url,
                'caption': caption
            },
            timeout=20
        )
        logger.info(f"Image sent to {phone}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send image: {str(e)}")
        return None

def generate_thumbnail(prompt, token):
    try:
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF['app_id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": prompt[:100], "style": "youtube_trending"},
            timeout=30
        )
        data = response.json()
        return data.get('image_url') or data.get('url') or data.get('output')
    except Exception as e:
        logger.error(f"GLIF API error: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("🚀 WhatsApp Thumbnail Generator Started")
    serve(app, host='0.0.0.0', port=8000)
