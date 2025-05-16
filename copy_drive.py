from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - VERIFY THESE IN ULTRAMSG DASHBOARD
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"
INSTANCE_ID = "instance116714"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. First log the raw incoming data
        data = request.json
        logger.info(f"\n{'='*50}\nRAW INCOMING DATA:\n{data}\n{'='*50}")

        # 2. Handle verification
        if request.method == 'GET':
            if request.args.get('token') == ULTRA_MSG_TOKEN:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        # 3. Process ONLY message_received events
        if data.get('event') != 'message_received':
            return jsonify({"status": "ignored"})

        # 4. Extract message data
        msg = data.get('data', {})
        if not msg:
            return jsonify({"error": "No message data"}), 400

        phone = msg.get('from', '').split('@')[0]
        text = msg.get('body', '').strip()
        
        logger.info(f"Preparing to reply to {phone} for message: {text}")

        # 5. FORCE A TEST REPLY (change to your number)
        test_phone = "923190779215"  # <<< MUST CHANGE TO YOUR NUMBER
        test_message = f"🔔 BOT REPLY: You said '{text}'"
        
        # 6. DEBUG: Print the exact API call we'll make
        api_url = f"{BASE_URL}/messages/chat"
        api_data = {
            'token': ULTRA_MSG_TOKEN,
            'to': test_phone,
            'body': test_message
        }
        logger.info(f"ATTEMPTING TO SEND VIA:\nURL: {api_url}\nDATA: {api_data}")

        # 7. Make the API call with timeout
        try:
            start_time = time.time()
            response = requests.post(
                api_url,
                data=api_data,
                timeout=10
            )
            response_time = time.time() - start_time
            
            logger.info(f"API RESPONSE ({response_time:.2f}s): {response.status_code} - {response.text}")
            
            if response.status_code == 200 and response.json().get('sent'):
                logger.info("✅ REPLY SUCCESSFULLY SENT")
            else:
                logger.error("❌ REPLY FAILED - CHECK ULTRAMSG DASHBOARD")
            
            return jsonify({"status": "processed"})

        except Exception as e:
            logger.error(f"🚨 SEND ERROR: {str(e)}")
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logger.error(f"🔥 CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 BOT STARTED - AWAITING MESSAGES")
    serve(app, host='0.0.0.0', port=8000)
