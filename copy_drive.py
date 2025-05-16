from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    "ultramsg": {
        "token": "j0253a3npbpb7ikw",
        "instance_id": "instance116714",
        "base_url": "https://api.ultramsg.com/instance116714"
    }
}

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Verification challenge
    if request.method == 'GET':
        if request.args.get('token') == CONFIG['ultramsg']['token']:
            return request.args.get('challenge', '')
        return "Invalid token", 403
    
    # Process messages
    data = request.json
    logger.info(f"Incoming message: {data}")
    
    if data and data.get('event') == 'message_received':
        msg = data.get('data', {})
        phone = msg.get('from', '').split('@')[0]
        text = msg.get('body', '').strip().lower()
        
        # Simple echo reply - proof it's working
        send_whatsapp_message(phone, f"Bot received: {text}")
        
        # Add your thumbnail generation logic here
        if text.startswith('generate'):
            topic = text.replace('generate', '').strip()
            if topic:
                send_whatsapp_message(phone, f"🚀 Generating thumbnail for: {topic}...")
                # Add your GLIF API call here
    
    return jsonify({'status': 'success'})

def send_whatsapp_message(phone, text):
    try:
        response = requests.post(
            f"{CONFIG['ultramsg']['base_url']}/messages/chat",
            data={
                'token': CONFIG['ultramsg']['token'],
                'to': phone,
                'body': text
            },
            timeout=10
        )
        logger.info(f"Message sent to {phone}: {text}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("Starting WhatsApp Bot Server...")
    serve(app, host='0.0.0.0', port=8000)
