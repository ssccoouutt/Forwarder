from flask import Flask, request, jsonify
import requests
from waitress import serve

app = Flask(__name__)

# UltraMSG Configuration
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"

@app.route('/')
def health_check():
    """Endpoint for Koyeb health checks"""
    return jsonify({"status": "healthy", "service": "WhatsApp Bot"})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """UltraMSG webhook endpoint"""
    # Verification challenge (GET request)
    if request.method == 'GET':
        if request.args.get('token') == ULTRA_MSG_TOKEN:
            return request.args.get('challenge')
        return "Invalid token", 403
    
    # Message processing (POST request)
    data = request.json
    print(f"Incoming webhook: {data}")  # Debug log
    
    if data and data.get('event') == 'message_received':
        msg = data.get('data', {})
        phone = msg.get('from', '').split('@')[0]
        text = msg.get('body', '').strip()
        
        # Simple echo reply
        requests.post(
            "https://api.ultramsg.com/instance116714/messages/chat",
            data={
                'token': ULTRA_MSG_TOKEN,
                'to': phone,
                'body': f"Echo: {text}"
            }
        )
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8000)
