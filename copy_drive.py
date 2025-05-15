from flask import Flask, request, jsonify
import requests
import time
from waitress import serve
import threading

app = Flask(__name__)

# ========== CONFIGURATION (HARDCODED VALUES) ========== #
ULTRA_MSG_INSTANCE_ID = "instance116714"
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"
ULTRA_MSG_URL = f"https://api.ultramsg.com/{ULTRA_MSG_INSTANCE_ID}"

GLIF_APP_ID = "cm0zceq2a00023f114o6hti7w"
GLIF_TOKENS = [
    "glif_a4ef6d3aa5d8575ea8448b29e293919a42a6869143fcbfc32f2e4a7dbe53199a",
    "glif_51d216db54438b777c4170cd8913d628ff0af09789ed5dbcbd718fa6c6968bb1",
    "glif_c9dc66b31537b5a423446bbdead5dc2dbd73dc1f4a5c47a9b77328abcbc7b755",
    "glif_f5a55ee6d767b79f2f3af01c276ec53d14475eace7cabf34b22f8e5968f3fef5",
    "glif_c3a7fd4779b59f59c08d17d4a7db46beefa3e9e49a9ebc4921ecaca35c556ab7",
    "glif_b31fdc2c9a7aaac0ec69d5f59bf05ccea0c5786990ef06b79a1d7db8e37ba317"
]

# ========== FLASK ROUTES ========== #
@app.route('/health')
def health_check():
    """Instant health check response for Koyeb"""
    return jsonify({'status': 'healthy', 'timestamp': time.time()}), 200

@app.route('/', methods=['GET', 'POST'])
def main_endpoint():
    """Handle all incoming requests"""
    if request.method == 'GET':
        return jsonify({'status': 'ready', 'service': 'WhatsApp Thumbnail Generator'}), 200
    
    return process_whatsapp_webhook()

# ========== CORE FUNCTIONALITY ========== #
def process_whatsapp_webhook():
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        print(f"Incoming webhook data: {data}")

        if data.get('event_type') == 'message_received':
            msg_data = data.get('data', {})
            phone = msg_data.get('from', '').split('@')[0]
            message = msg_data.get('body', '').strip().lower()
            
            if not message:
                return jsonify({'status': 'error', 'message': 'Empty message'}), 400

            # Command processing
            if message in ['hi', 'hello', 'hey']:
                return send_whatsapp_reply(phone, "👋 Hi! Send me a video topic to generate a thumbnail!")
                
            elif message in ['help', 'info']:
                return send_whatsapp_reply(phone, "ℹ️ Just send me a topic (e.g. 'cooking tutorial') and I'll create a thumbnail!")
                
            elif len(message) > 3:
                send_whatsapp_reply(phone, "🔄 Generating thumbnail... (20-30 seconds)")
                
                for token in GLIF_TOKENS:
                    image_url = generate_with_glif(message, token)
                    if image_url:
                        send_whatsapp_image(phone, image_url, f"🎨 Thumbnail for: {message}")
                        send_whatsapp_reply(phone, f"🔗 Direct URL: {image_url}")
                        return jsonify({'status': 'success'})
                
                return send_whatsapp_reply(phone, "❌ All generation attempts failed. Try different keywords.")
            
        return jsonify({'status': 'ignored', 'reason': 'unhandled_event_type'}), 200
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ========== SERVICE FUNCTIONS ========== #
def send_whatsapp_reply(phone, text, retries=3):
    """Send WhatsApp text message with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{ULTRA_MSG_URL}/messages/chat",
                data={
                    'token': ULTRA_MSG_TOKEN,
                    'to': phone,
                    'body': text
                },
                timeout=10
            )
            return jsonify(response.json())
        except Exception as e:
            print(f"Message send attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2)
    return None

def send_whatsapp_image(phone, image_url, caption, retries=3):
    """Send WhatsApp image with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{ULTRA_MSG_URL}/messages/image",
                data={
                    'token': ULTRA_MSG_TOKEN,
                    'to': phone,
                    'image': image_url,
                    'caption': caption
                },
                timeout=20
            )
            return response.json()
        except Exception as e:
            print(f"Image send attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2)
    return None

def generate_with_glif(prompt, token, max_length=100):
    """Generate thumbnail using GLIF API"""
    try:
        print(f"Generating thumbnail for: {prompt[:max_length]}")
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF_APP_ID}",
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
                print(f"Successfully generated image: {data[key]}")
                return data[key]
        
        print(f"Unexpected GLIF response: {data}")
        return None
        
    except Exception as e:
        print(f"GLIF API error: {str(e)}")
        return None

# ========== SERVER SETUP ========== #
def run_server():
    """Start production WSGI server"""
    print("Starting production server on port 8000")
    serve(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    print("""
    ███████╗██╗  ██╗██████╗ ███████╗██████╗ 
    ██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔══██╗
    █████╗   ╚███╔╝ ██████╔╝█████╗  ██████╔╝
    ██╔══╝   ██╔██╗ ██╔═══╝ ██╔══╝  ██╔══██╗
    ███████╗██╔╝ ██╗██║     ███████╗██║  ██║
    ╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝
    WhatsApp Thumbnail Generator Service
    """)
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Keep main thread alive
    while True:
        time.sleep(3600)  # Sleep for 1 hour
