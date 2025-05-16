from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - VERIFY THESE VALUES
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"
INSTANCE_ID = "instance116714"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. Log incoming request details
        logger.info(f"\n{'='*50}\nINCOMING REQUEST:\n"
                   f"Method: {request.method}\n"
                   f"Headers: {dict(request.headers)}\n"
                   f"Args: {request.args}\n"
                   f"JSON: {request.json}\n"
                   f"{'='*50}")

        # 2. Handle verification
        if request.method == 'GET':
            token = request.args.get('token')
            if token == ULTRA_MSG_TOKEN:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        # 3. Process message
        data = request.json
        if data and data.get('event') == 'message_received':
            msg = data['data']
            phone = msg['from'].split('@')[0]
            text = msg.get('body', '').strip()
            
            logger.info(f"Processing message from {phone}: {text}")

            # 4. Try sending reply (TEST WITH YOUR NUMBER)
            test_phone = "923190779215"  # <<< CHANGE TO YOUR NUMBER
            test_message = f"🔔 Bot reply to: {text}"
            
            # Method 1: Standard API call
            api_result = send_message(test_phone, test_message)
            logger.info(f"API RESULT: {api_result}")

            return jsonify({
                "status": "processed",
                "reply_attempted": True,
                "api_result": api_result
            })

        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_message(phone, text):
    """Send message with thorough error handling"""
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/messages/chat",
            data={
                'token': ULTRA_MSG_TOKEN,
                'to': phone,
                'body': text
            },
            timeout=10
        )
        response_data = {
            "status_code": response.status_code,
            "response": response.text,
            "time_taken": f"{time.time()-start_time:.2f}s",
            "success": response.json().get('sent', False)
        }
        logger.info(f"MESSAGE API RESPONSE: {response_data}")
        return response_data
    except Exception as e:
        logger.error(f"SEND ERROR: {str(e)}")
        return {"error": str(e)}

if __name__ == '__main__':
    logger.info("🚀 WhatsApp Bot Started - Ready for Messages")
    serve(app, host='0.0.0.0', port=8000)
