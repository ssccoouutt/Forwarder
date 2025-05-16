from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
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
    ],
    "styles": ["youtube_trending", "digital_art", "cinematic"],
    "timeout": 35
}

# ===== FLASK ROUTES =====
@app.route('/')
def health_check():
    return jsonify({
        "status": "ready",
        "service": "WhatsApp Thumbnail Generator",
        "endpoints": {
            "webhook": "POST /webhook",
            "health": "GET /"
        }
    })

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # Verification challenge
        if request.method == 'GET':
            if request.args.get('token') == ULTRA_MSG["token"]:
                logger.info("Webhook verified successfully")
                return request.args.get('challenge', '')
            logger.warning("Invalid verification token")
            return "Invalid token", 403

        data = request.json
        if not data:
            logger.error("No data received in webhook")
            return jsonify({"error": "No data received"}), 400

        logger.info(f"Incoming message: {data.get('data', {}).get('from', '')}")

        if data.get('event') == 'message_received':
            return process_message(data.get('data', {}))
        
        logger.info(f"Ignoring event: {data.get('event')}")
        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

# ===== CORE FUNCTIONALITY =====
def process_message(msg):
    phone = msg.get('from', '').split('@')[0]
    text = msg.get('body', '').strip().lower()

    # Command processing
    if not text:
        logger.warning("Empty message received")
        return send_message(phone, "❌ Please send a valid message")

    if text in ['hi', 'hello', 'hey']:
        return send_message(phone, "👋 Send me a topic to generate a thumbnail!\nExample: 'mountain sunset'")

    if text in ['help', 'info']:
        help_text = (
            "ℹ️ *Thumbnail Generator Help*\n\n"
            "Just send me a topic and I'll create a thumbnail!\n"
            "Examples:\n"
            "- 'cyberpunk city'\n"
            "- 'sunset beach'\n"
            "- 'cooking tutorial'\n\n"
            "I'll generate different styles automatically!"
        )
        return send_message(phone, help_text)

    # Generate thumbnail
    send_message(phone, "🔄 Generating your thumbnail... (30-45 seconds)")
    
    generated = False
    for style in GLIF["styles"]:
        for token in GLIF["tokens"]:
            image_url = generate_thumbnail(text, token, style)
            if image_url:
                send_image(phone, image_url, f"🎨 {text.title()} ({style.replace('_', ' ')})")
                send_message(phone, f"🔗 Direct URL: {image_url}")
                generated = True
                break
        if generated:
            break

    if not generated:
        send_message(phone, "❌ All generation attempts failed. Please try different keywords later.")
    
    return jsonify({"status": "success" if generated else "failed"})

# ===== SERVICE FUNCTIONS =====
def send_message(phone, text, retries=3):
    for attempt in range(retries):
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
            logger.info(f"Message sent to {phone} (attempt {attempt + 1})")
            return response.json()
        except Exception as e:
            logger.warning(f"Message send failed (attempt {attempt + 1}): {str(e)}")
            time.sleep(2)
    logger.error(f"Failed to send message to {phone} after {retries} attempts")
    return None

def send_image(phone, url, caption, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{ULTRA_MSG['base_url']}/messages/image",
                data={
                    'token': ULTRA_MSG['token'],
                    'to': phone,
                    'image': url,
                    'caption': caption
                },
                timeout=25
            )
            logger.info(f"Image sent to {phone} (attempt {attempt + 1})")
            return response.json()
        except Exception as e:
            logger.warning(f"Image send failed (attempt {attempt + 1}): {str(e)}")
            time.sleep(2)
    logger.error(f"Failed to send image to {phone} after {retries} attempts")
    return None

def generate_thumbnail(prompt, token, style, max_length=100):
    try:
        logger.info(f"Generating thumbnail: {prompt} ({style})")
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF['app_id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": prompt[:max_length],
                "style": style,
                "negative_prompt": "blurry, low quality, text, watermark"
            },
            timeout=GLIF["timeout"]
        )
        data = response.json()
        
        # Check all possible response formats
        for key in ["output", "image_url", "url"]:
            if key in data and isinstance(data[key], str) and data[key].startswith('http'):
                logger.info(f"Successfully generated image: {data[key]}")
                return data[key]
        
        logger.warning(f"Unexpected GLIF response: {data}")
        return None
        
    except Exception as e:
        logger.error(f"GLIF API error: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("""
    ████████╗██╗  ██╗██╗   ██╗███╗   ███╗██████╗ 
    ╚══██╔══╝██║  ██║██║   ██║████╗ ████║██╔══██╗
       ██║   ███████║██║   ██║██╔████╔██║██████╔╝
       ██║   ██╔══██║██║   ██║██║╚██╔╝██║██╔═══╝ 
       ██║   ██║  ██║╚██████╔╝██║ ╚═╝ ██║██║     
       ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     
    WhatsApp Thumbnail Generator Service
    """)
    serve(app, host='0.0.0.0', port=8000)
