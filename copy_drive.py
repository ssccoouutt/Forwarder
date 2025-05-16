from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UltraMSG Configuration
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

# GLIF Configuration
GLIF_ID = "cm0zceq2a00023f114o6hti7w"
API_TOKENS = [
    "glif_a4ef6d3aa5d8575ea8448b29e293919a42a6869143fcbfc32f2e4a7dbe53199a",
    "glif_51d216db54438b777c4170cd8913d628ff0af09789ed5dbcbd718fa6c6968bb1",
    "glif_c9dc66b31537b5a423446bbdead5dc2dbd73dc1f4a5c47a9b77328abcbc7b755",
    "glif_f5a55ee6d767b79f2f3af01c276ec53d14475eace7cabf34b22f8e5968f3fef5",
    "glif_c3a7fd4779b59f59c08d17d4a7db46beefa3e9e49a9ebc4921ecaca35c556ab7",
    "glif_b31fdc2c9a7aaac0ec69d5f59bf05ccea0c5786990ef06b79a1d7db8e37ba317"
]

@app.route('/')
def health_check():
    """Endpoint for Koyeb health checks"""
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        logger.info(f"\n{'='*50}\nIncoming request: {request.method}")
        
        # Verification challenge
        if request.method == 'GET':
            if request.args.get('token') == TOKEN:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        data = request.json
        if not data:
            logger.error("No data received")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        logger.info(f"Request data: {data}")

        # Process messages
        if data.get('event_type') == 'message_received':
            msg_data = data.get('data', {})
            phone = msg_data.get('from', '').split('@')[0]
            message = msg_data.get('body', '').strip().lower()

            logger.info(f"Processing message from {phone}: {message}")

            # Command handling
            if message in ['hi', 'hello', 'hey']:
                send_message(phone, "👋 Hi! Send me any video topic to generate a thumbnail!")
                return jsonify({'status': 'success'})
                
            elif message in ['help', 'info']:
                send_message(phone, "ℹ️ Just send me a video topic (e.g. 'cooking tutorial') and I'll create a thumbnail!")
                return jsonify({'status': 'success'})
                
            # Thumbnail generation
            elif len(message) > 3:
                send_message(phone, "🔄 Generating your thumbnail... (20-30 seconds)")
                
                for token in API_TOKENS:
                    result = generate_thumbnail(message, token)
                    if result.get('status') == 'success':
                        send_image(phone, result['image_url'], f"🎨 Thumbnail for: {message}")
                        send_message(phone, f"🔗 Direct URL: {result['image_url']}")
                        return jsonify({'status': 'success'})
                
                send_message(phone, "❌ Failed to generate. Please try different keywords.")

        return jsonify({'status': 'ignored'})
    
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def send_message(phone, text, retries=3):
    """Send WhatsApp message with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/chat",
                data={'token': TOKEN, 'to': phone, 'body': text},
                timeout=10
            )
            logger.info(f"Message sent to {phone} (attempt {attempt+1})")
            return response.json()
        except Exception as e:
            logger.warning(f"Message send failed (attempt {attempt+1}): {str(e)}")
            time.sleep(2)
    logger.error(f"Failed to send message to {phone} after {retries} attempts")
    return None

def send_image(phone, url, caption, retries=3):
    """Send WhatsApp image with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/image",
                data={'token': TOKEN, 'to': phone, 'image': url, 'caption': caption},
                timeout=20
            )
            logger.info(f"Image sent to {phone} (attempt {attempt+1})")
            return response.json()
        except Exception as e:
            logger.warning(f"Image send failed (attempt {attempt+1}): {str(e)}")
            time.sleep(2)
    logger.error(f"Failed to send image to {phone} after {retries} attempts")
    return None

def generate_thumbnail(prompt, token, max_length=100):
    """Generate thumbnail using GLIF API"""
    try:
        logger.info(f"Generating thumbnail for: {prompt[:max_length]}")
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF_ID}",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": prompt[:max_length], "style": "youtube_trending"},
            timeout=30
        )
        data = response.json()
        
        # Check all possible response formats
        for key in ["output", "image_url", "url"]:
            if key in data and isinstance(data[key], str) and data[key].startswith('http'):
                logger.info(f"Successfully generated image: {data[key]}")
                return {'status': 'success', 'image_url': data[key]}
        
        logger.warning(f"Unexpected GLIF response: {data}")
        return {'status': 'error'}
        
    except Exception as e:
        logger.error(f"GLIF API error: {str(e)}")
        return {'status': 'error'}

if __name__ == '__main__':
    logger.info("Starting WhatsApp Thumbnail Generator...")
    serve(app, host='0.0.0.0', port=8000)
