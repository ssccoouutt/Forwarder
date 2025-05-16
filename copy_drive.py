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
        token = request.args.get('token')
        if token == CONFIG['ultramsg']['token']:
            logger.info("Verification successful")
            return request.args.get('challenge', '')
        logger.warning(f"Invalid token received: {token}")
        return "Invalid token", 403
    
    # Process messages
    data = request.json
    logger.info(f"Incoming message data: {data}")
    
    if data and data.get('event') == 'message_received':
        msg = data.get('data', {})
        phone = msg.get('from', '').split('@')[0]
        text = msg.get('body', '').strip().lower()
        
        logger.info(f"Processing message from {phone}: {text}")
        
        # Always reply to test the connection
        reply = f"🤖 Bot received: {text}"
        send_response = send_whatsapp_message(phone, reply)
        
        if send_response:
            logger.info(f"Reply sent successfully: {reply}")
        else:
            logger.error("Failed to send reply")
    
    return jsonify({'status': 'processed'})

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
        logger.info(f"Message API response: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return None

if __name__ == '__main__':
    logger.info("🚀 Starting WhatsApp Bot Server...")
    serve(app, host='0.0.0.0', port=8000)
