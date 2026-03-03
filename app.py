from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json
import os
import asyncio
import threading
from trading_bot import TradingBot

app = Flask(__name__)
socketio = SocketIO(app)
bot = TradingBot(socketio)

SETTINGS_FILE = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_settings', methods=['POST'])
def save_configs():
    settings = request.json
    save_settings(settings)
    return jsonify({'status': 'success'})

@app.route('/toggle_bot', methods=['POST'])
def toggle_bot():
    if bot.is_running:
        asyncio.run_coroutine_threadsafe(bot.stop(), bot_loop)
    else:
        settings = load_settings()
        if not settings.get('api_token'):
            return jsonify({'status': 'error', 'message': 'Missing API Token'})
        asyncio.run_coroutine_threadsafe(bot.start(settings), bot_loop)
    return jsonify({'status': 'success'})

def start_bot_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':
    bot_loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_bot_loop, args=(bot_loop,), daemon=True)
    t.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
