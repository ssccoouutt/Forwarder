from flask import Flask, request, jsonify
import requests
import time
from waitress import serve  # Production-grade WSGI server

app = Flask(__name__)

# UltraMSG Configuration (HARDCODED VALUES)
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

# GLIF Configuration (HARDCODED VALUES)
GLIF_ID = "cm0zceq2a00023f114o6hti7w"
API_TOKENS = [
    "glif_a4ef6d3aa5d8575ea8448b29e293919a42a6869143fcbfc32f2e4a7dbe53199a",
    "glif_51d216db54438b777c4170cd8913d628ff0af09789ed5dbcbd718fa6c6968bb1",
    "glif_c9dc66b31537b5a423446bbdead5dc2dbd73dc1f4a5c47a9b77328abcbc7b755",
    "glif_f5a55ee6d767b79f2f3af01c276ec53d14475eace7cabf34b22f8e5968f3fef5",
    "glif_c3a7fd4779b59f59c08d17d4a7db46beefa3e9e49a9ebc4921ecaca35c556ab7",
    "glif_b31fdc2c9a7aaac0ec69d5f59bf05ccea0c5786990ef06b79a1d7db8e37ba317"
]

@app.route('/', methods=['POST'])
def webhook():
    try:
        print("\nIncoming WhatsApp webhook request")
        
        if not request.json:
            print("Empty request received")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        data = request.json
        print(f"Processing message: {data}")

        # UltraMSG message format handling
        if data.get('event_type') == 'message_received':
            msg_data = data.get('data', {})
            phone = msg_data.get('from', '').split('@')[0]  # Remove @c.us suffix
            message = msg_data.get('body', '').strip().lower()
            
            # Command router
            if not message:
                return jsonify({'status': 'error', 'message': 'Empty message'}), 400
                
            if message in ['hi', 'hello', 'hey']:
                return process_response(phone, "👋 Hi! Send me any video topic to generate a thumbnail!")
                
            elif message in ['help', 'info']:
                return process_response(phone, "ℹ️ Just send me a topic (e.g. 'cooking tutorial') and I'll create a thumbnail!")
                
            elif len(message) > 3:
                process_response(phone, "🔄 Generating your thumbnail... (20-30 seconds)")
                
                # Try all GLIF tokens until success
                for token in API_TOKENS:
                    image_url = generate_thumbnail(message, token)
                    if image_url:
                        send_whatsapp_image(phone, image_url, f"🎨 Thumbnail for: {message}")
                        process_response(phone, f"🔗 Direct URL: {image_url}")
                        return jsonify({'status': 'success'})
                
                # All tokens failed
                return process_response(phone, "❌ All generation attempts failed. Try different keywords.")
            
            return jsonify({'status': 'ignored'})
            
        return jsonify({'status': 'unhandled_event'})
    
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_response(phone, text):
    """Handle WhatsApp text response with retry logic"""
    print(f"Sending message to {phone}: {text}")
    for attempt in range(3):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/chat",
                data={'token': TOKEN, 'to': phone, 'body': text},
                timeout=10
            )
            return jsonify(response.json())
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2)
    return jsonify({'status': 'error', 'message': 'Failed to send response'})

def send_whatsapp_image(phone, image_url, caption):
    """Send image through WhatsApp with retry logic"""
    print(f"Sending image to {phone}: {image_url}")
    for attempt in range(3):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/image",
                data={
                    'token': TOKEN,
                    'to': phone,
                    'image': image_url,
                    'caption': caption
                },
                timeout=20
            )
            return response.json()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2)
    return None

def generate_thumbnail(prompt, token):
    """Generate thumbnail using GLIF API"""
    print(f"Generating thumbnail for: {prompt}")
    try:
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF_ID}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": prompt[:100],  # Truncate to 100 chars
                "style": "youtube_trending"
            },
            timeout=30
        )
        data = response.json()
        
        # Check multiple possible response formats
        for key in ["output", "image_url", "url"]:
            if key in data and isinstance(data[key], str) and data[key].startswith('http'):
                print(f"Successfully generated image: {data[key]}")
                return data[key]
        
        print(f"Unexpected GLIF response format: {data}")
        return None
        
    except Exception as e:
        print(f"GLIF API error: {str(e)}")
        return None

if __name__ == '__main__':
    print("Starting WhatsApp Thumbnail Bot Server")
    serve(app, host="0.0.0.0", port=8000)  # Production server on Koyeb's expected port
