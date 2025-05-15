from flask import Flask, request, jsonify
import requests
import time
from waitress import serve
import sys

app = Flask(__name__)

# ===== CONFIGURATION =====
ULTRA_MSG = {
    "instance_id": "instance116714",
    "token": "j0253a3npbpb7ikw",
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

# ===== INSTANT HEALTH CHECK =====
@app.route('/')
def health_check():
    """Instant response health check"""
    return jsonify({
        'status': 'ready',
        'service': 'WhatsApp Thumbnail Generator',
        'timestamp': int(time.time())
    })

# ===== WEBHOOK ENDPOINT =====
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Process WhatsApp messages"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data received'}), 400

        # UltraMSG verification
        if request.args.get('verify_token') == ULTRA_MSG['token']:
            return request.args.get('challenge')

        # Process messages
        if data.get('event') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').strip().lower()

            if not text:
                return jsonify({'error': 'Empty message'}), 400

            if text in ['hi', 'hello', 'hey']:
                return send_message(phone, "👋 Hi! Send me a video topic!")

            if text in ['help', 'info']:
                return send_message(phone, "ℹ️ Send me a topic (e.g. 'cooking tutorial')")

            if len(text) > 3:
                send_message(phone, "🔄 Generating thumbnail...")
                for token in GLIF['tokens']:
                    img_url = generate_image(text, token)
                    if img_url:
                        send_image(phone, img_url, f"🎨 {text}")
                        return jsonify({'success': True})

                return send_message(phone, "❌ Failed to generate thumbnail")

        return jsonify({'status': 'ignored'}), 200

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

# ===== SERVICE FUNCTIONS =====
def send_message(phone, text):
    """Send WhatsApp message"""
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
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to send message: {str(e)}", file=sys.stderr)
        return jsonify({'error': 'Failed to send'}), 500

def send_image(phone, url, caption):
    """Send WhatsApp image"""
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
        return response.json()
    except Exception as e:
        print(f"Failed to send image: {str(e)}", file=sys.stderr)
        return None

def generate_image(prompt, token):
    """Generate thumbnail"""
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
        print(f"Failed to generate image: {str(e)}", file=sys.stderr)
        return None

if __name__ == '__main__':
    print("Starting WhatsApp Thumbnail Service...", file=sys.stderr)
    serve(app, host='0.0.0.0', port=8000)
