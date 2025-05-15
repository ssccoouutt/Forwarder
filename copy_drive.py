from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

# UltraMSG Configuration - HARDCODED
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

# GLIF Configuration - HARDCODED
GLIF_ID = "cm0zceq2a00023f114o6hti7w"
API_TOKENS = [
    "glif_a4ef6d3aa5d8575ea8448b29e293919a42a6869143fcbfc32f2e4a7dbe53199a",
    "glif_51d216db54438b777c4170cd8913d628ff0af09789ed5dbcbd718fa6c6968bb1",
    "glif_c9dc66b31537b5a423446bbdead5dc2dbd73dc1f4a5c47a9b77328abcbc7b755",
    "glif_f5a55ee6d767b79f2f3af01c276ec53d14475eace7cabf34b22f8e5968f3fef5",
    "glif_c3a7fd4779b59f59c08d17d4a7db46beefa3e9e49a9ebc4921ecaca35c556ab7",
    "glif_b31fdc2c9a7aaac0ec69d5f59bf05ccea0c5786990ef06b79a1d7db8e37ba317"
]

@app.route('/', methods=['GET', 'POST'])
def webhook():
    try:
        print("\nIncoming request detected")
        
        if not request.json:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        data = request.json
        if data.get('event_type') == 'message_received':
            msg_data = data.get('data', {})
            phone = msg_data.get('from', '').split('@')[0]
            message = msg_data.get('body', '').strip().lower()
            
            # Command router
            if message in ['hi', 'hello', 'hey']:
                return respond(phone, "👋 Hi! Send me any video topic to generate a thumbnail!")
                
            elif message in ['help', 'info']:
                return respond(phone, "ℹ️ Just send me a topic (e.g. 'cooking tutorial') and I'll create a thumbnail!")
                
            elif len(message) > 3:
                respond(phone, "🔄 Generating your thumbnail... (20-30 seconds)")
                
                for token in API_TOKENS:
                    image_url = generate_image(message, token)
                    if image_url:
                        send_image(phone, image_url, f"🎨 Thumbnail for: {message}")
                        respond(phone, f"🔗 Direct URL: {image_url}")
                        return jsonify({'status': 'success'})
                
                respond(phone, "❌ All generation attempts failed. Try different keywords.")
                return jsonify({'status': 'error'})
        
        return jsonify({'status': 'ignored'})
    
    except Exception as e:
        print(f"CRASH: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def respond(phone, text):
    """UltraMSG message sender with brute-force retry"""
    for _ in range(3):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/chat",
                data={'token': TOKEN, 'to': phone, 'body': text},
                timeout=10
            )
            return response.json()
        except:
            time.sleep(2)
    return None

def send_image(phone, url, caption):
    """UltraMSG image sender with brute-force retry"""
    for _ in range(3):
        try:
            response = requests.post(
                f"{BASE_URL}/messages/image",
                data={'token': TOKEN, 'to': phone, 'image': url, 'caption': caption},
                timeout=20
            )
            return response.json()
        except:
            time.sleep(2)
    return None

def generate_image(prompt, token):
    """GLIF API caller with aggressive error handling"""
    try:
        response = requests.post(
            f"https://simple-api.glif.app/{GLIF_ID}",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": prompt[:100], "style": "youtube_trending"},
            timeout=30
        )
        
        # Parse every possible response format
        data = response.json()
        for key in ["output", "image_url", "url"]:
            if key in data and isinstance(data[key], str) and data[key].startswith('http'):
                return data[key]
                
        print(f"Strange GLIF response: {data}")
        return None
        
    except Exception as e:
        print(f"GLIF explosion: {str(e)}")
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)  # Koyeb's default port
