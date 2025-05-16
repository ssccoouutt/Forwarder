from flask import Flask, request, jsonify
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UltraMSG Configuration
INSTANCE_ID = "instance116714"
TOKEN = "j0253a3npbpb7ikw"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

# Test Image
IMAGE_URL = "https://cdn.indexer.eu.org/-1002243289687/107/1747349785/ebc621f06a95452721ccee05308099f8f140799b6749666e85e66b72da902c13"

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logger.info(f"INCOMING DATA: {data}")
        
        if data.get('event_type') == 'message_received':
            msg = data.get('data', {})
            phone = msg.get('from', '').split('@')[0]
            text = msg.get('body', '').lower().strip()
            
            logger.info(f"Processing message from {phone}: {text}")
            
            # Reply to all messages with image
            response = requests.post(
                f"{BASE_URL}/messages/image",
                data={
                    'token': TOKEN,
                    'to': phone,
                    'image': IMAGE_URL,
                    'caption': f"Hello! You said: {text}"
                },
                timeout=10
            )
            
            logger.info(f"ULTRA MSG API RESPONSE: {response.status_code} - {response.text}")
            
        return jsonify({'status': 'success'})
    
    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    from waitress import serve
    logger.info("Starting server on port 8000...")
    serve(app, host='0.0.0.0', port=8000)
