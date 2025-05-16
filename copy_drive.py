from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UltraMSG Configuration
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"
INSTANCE_ID = "instance116714"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. Handle verification challenge
        if request.method == 'GET':
            if request.args.get('token') == ULTRA_MSG_TOKEN:
                return request.args.get('challenge', '')
            return "Invalid token", 403

        # 2. Process incoming messages
        data = request.json
        logger.info(f"RAW INCOMING DATA:\n{data}")

        if data.get('event') == 'message_received':
            msg = data['data']
            phone = msg['from'].split('@')[0]  # Remove @c.us
            text = msg.get('body', '').lower().strip()

            # 3. DEBUG: Immediate test reply
            test_reply = f"✅ Bot working! You said: {text}"
            send_result = send_message(phone, test_reply)
            
            if not send_result:
                logger.error("FAILED TO SEND REPLY")
            else:
                logger.info(f"REPLY SENT TO {phone}")

        return jsonify({"status": "processed"})

    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_message(phone, text):
    """Send message with ULTRA-THOROUGH error handling"""
    for attempt in range(3):  # 3 retries
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
            logger.info(f"API RESPONSE ({time.time()-start_time:.2f}s): {response.status_code} - {response.text}")
            
            if response.json().get('sent') is True:
                return True
                
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            time.sleep(2)
    
    return False

if __name__ == '__main__':
    logger.info("🔥 BOT STARTED - WAITING FOR MESSAGES 🔥")
    serve(app, host='0.0.0.0', port=8000)
