from flask import Flask, request, jsonify
from waitress import serve
import requests
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - TRIPLE-CHECK THESE VALUES
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"
INSTANCE_ID = "instance116714"
BASE_URL = f"https://api.ultramsg.com/{INSTANCE_ID}"

@app.route('/')
def health_check():
    return jsonify({"status": "ready"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # 1. First log EVERYTHING about the incoming request
        logger.info(f"\n{'='*50}\nINCOMING REQUEST:\n"
                   f"Method: {request.method}\n"
                   f"Headers: {dict(request.headers)}\n"
                   f"Args: {request.args}\n"
                   f"Data: {request.data}\n"
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
        if data.get('event') == 'message_received':
            msg = data['data']
            phone = msg['from'].split('@')[0]  # 923190779215
            text = msg.get('body', '').strip()
            
            logger.info(f"Preparing to reply to {phone}...")

            # 4. TEST: Try sending to YOUR personal number first
            test_phone = "923190779215"  # <<< CHANGE TO YOUR NUMBER
            test_message = f"🚨 TEST REPLY to {phone} for message: {text}"
            
            # 5. DEBUG: Try THREE different sending methods
            send_results = {
                "method1": send_via_ultramsg_api(test_phone, test_message),
                "method2": send_via_requests_direct(test_phone, test_message),
                "method3": send_via_curl_command(test_phone, test_message)
            }
            
            logger.info(f"SEND RESULTS:\n{send_results}")
            
            return jsonify({"status": "processed", "results": send_results})

        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_via_ultramsg_api(phone, text):
    """Method 1: Standard UltraMSG API"""
    try:
        response = requests.post(
            f"{BASE_URL}/messages/chat",
            data={'token': ULTRA_MSG_TOKEN, 'to': phone, 'body': text},
            timeout=10
        )
        return {
            "status": response.status_code,
            "response": response.text,
            "success": response.json().get('sent', False)
        }
    except Exception as e:
        return {"error": str(e)}

def send_via_requests_direct(phone, text):
    """Method 2: Direct request with debug"""
    try:
        response = requests.post(
            "https://api.ultramsg.com/instance116714/messages/chat",
            data={'token': ULTRA_MSG_TOKEN, 'to': phone, 'body': text},
            timeout=10
        )
        return {
            "url": response.url,
            "status": response.status_code,
            "headers": dict(response.headers),
            "response": response.text
        }
    except Exception as e:
        return {"error": str(e)}

def send_via_curl_command(phone, text):
    """Method 3: Returns curl command you can run manually"""
    return {
        "curl_command": f"""curl -X POST \\
        "https://api.ultramsg.com/instance116714/messages/chat" \\
        -d "token=j0253a3npbpb7ikw" \\
        -d "to={phone}" \\
        -d "body={text.replace(' ', '+')}""""
    }

if __name__ == '__main__':
    logger.info("🚀 STARTING DEBUG BOT - WILL LOG EVERYTHING 🚀")
    serve(app, host='0.0.0.0', port=8000)
