from flask import Flask, request, jsonify
import requests
import time
from waitress import serve
import threading
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

# ===== HEALTH MANAGEMENT =====
service_ready = False

@app.route('/health')
def health_check():
    """Comprehensive health endpoint for Koyeb"""
    if service_ready:
        return jsonify({
            'status': 'healthy',
            'service': 'WhatsApp Thumbnail Bot',
            'timestamp': int(time.time()),
            'system': {
                'python_version': sys.version,
                'platform': sys.platform
            }
        }), 200
    return jsonify({'status': 'starting'}), 503

@app.route('/')
def ready_check():
    """Root endpoint for basic health checks"""
    return jsonify({
        'status': 'ready' if service_ready else 'starting',
        'service': 'WhatsApp Thumbnail Generator',
        'endpoints': {
            'health': '/health',
            'webhook': 'POST /'
        }
    }), 200 if service_ready else 503

# ===== CORE FUNCTIONALITY =====
@app.route('/', methods=['POST'])
def webhook_handler():
    """Main UltraMSG webhook processor"""
    try:
        if not service_ready:
            return jsonify({'error': 'Service initializing'}), 503

        data = request.json
        if not data:
            return jsonify({'error': 'No data received'}), 400

        # Process UltraMSG webhook format
        if data.get('event_type') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').strip().lower()

            if not text:
                return jsonify({'error': 'Empty message'}), 400

            # Command processing
            if text in ['hi', 'hello', 'hey']:
                return send_response(phone, "👋 Hi! Send me a video topic to generate a thumbnail!")

            if text in ['help', 'info']:
                return send_response(phone, "ℹ️ Send me a topic (e.g. 'cooking tutorial') and I'll create a thumbnail!")

            if len(text) > 3:
                send_response(phone, "🔄 Generating thumbnail... (20-30 seconds)")
                
                for token in GLIF['tokens']:
                    image_url = generate_thumbnail(text, token)
                    if image_url:
                        send_image(phone, image_url, f"🎨 Thumbnail for: {text}")
                        send_response(phone, f"🔗 Direct URL: {image_url}")
                        return jsonify({'success': True})

                return send_response(phone, "❌ All generation attempts failed. Try different keywords.")

        return jsonify({'status': 'ignored'}), 200

    except Exception as e:
        print(f"ERROR: {str(e)}", flush=True)
        return jsonify({'error': str(e)}), 500

# ===== SERVICE FUNCTIONS =====
def send_response(phone, text, retries=3):
    """Send WhatsApp message with retry logic"""
    for attempt in range(retries):
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
            print(f"Attempt {attempt + 1} failed: {str(e)}", flush=True)
            time.sleep(2)
    return jsonify({'error': 'Failed to send message'}), 500

def send_image(phone, url, caption, retries=3):
    """Send WhatsApp image with retry logic"""
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
                timeout=20
            )
            return response.json()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}", flush=True)
            time.sleep(2)
    return None

def generate_thumbnail(prompt, token, max_length=100):
    """Generate image using GLIF API"""
    try:
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF['app_id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": prompt[:max_length],
                "style": "youtube_trending"
            },
            timeout=30
        )
        data = response.json()
        
        # Check all possible response formats
        for key in ["output", "image_url", "url"]:
            if key in data and isinstance(data[key], str) and data[key].startswith('http'):
                return data[key]
        
        print(f"Unexpected GLIF response: {data}", flush=True)
        return None
        
    except Exception as e:
        print(f"GLIF API error: {str(e)}", flush=True)
        return None

# ===== SERVER MANAGEMENT =====
def run_server():
    """Start production server"""
    global service_ready
    print("Starting production server on port 8000", flush=True)
    serve(app, host="0.0.0.0", port=8000)
    service_ready = True

if __name__ == '__main__':
    print("""
    WhatsApp Thumbnail Generator Service
    Initializing at {}...
    """.format(time.ctime()), flush=True)

    # Start server in background
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    # Mark service as ready after initialization
    time.sleep(2)  # Allow server to start
    service_ready = True
    print("Service is now ready", flush=True)

    # Keep main thread alive
    while True:
        time.sleep(3600)
