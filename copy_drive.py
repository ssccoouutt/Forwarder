from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# UltraMSG Configuration
ULTRA_MSG_TOKEN = "j0253a3npbpb7ikw"

@app.route('/', methods=['GET', 'POST'])
def webhook():
    # Verify token (GET request from UltraMSG)
    if request.method == 'GET':
        if request.args.get('token') == ULTRA_MSG_TOKEN:
            return request.args.get('challenge')
        return "Invalid token", 403
    
    # Process messages (POST request)
    data = request.json
    print(f"Incoming webhook data: {data}")  # Debug log
    
    # Simple echo response
    if data and data.get('event') == 'message_received':
        phone = data['data']['from'].split('@')[0]
        message = data['data']['body']
        
        # Send reply back
        requests.post(
            f"https://api.ultramsg.com/instance116714/messages/chat",
            data={
                'token': ULTRA_MSG_TOKEN,
                'to': phone,
                'body': f"You said: {message}"
            }
        )
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
