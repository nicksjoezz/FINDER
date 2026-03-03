from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json
import os
import asyncio
import threading
from trading_bot import TradingBot
import pandas as pd
from datetime import datetime, timedelta
from deriv_api import DerivAPI
from strategy_utils import ut_bot, Backtester, calculate_max_consecutive_losses
from indicators import add_indicators

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

async def get_bt_data(symbol, days):
    # Caching logic
    cache_file = f"data/cache_{symbol}_{days}d.csv"
    if os.path.exists(cache_file):
        # Check if cache is fresh (less than 1 hour old)
        if (datetime.now().timestamp() - os.path.getmtime(cache_file)) < 3600:
            return pd.read_csv(cache_file)

    api = DerivAPI(app_id=1089)
    end = int(datetime.now().timestamp())
    start = end - (int(days) * 86400)

    all_candles = []
    curr = end
    while curr > start:
        resp = await api.ticks_history({
            'ticks_history': symbol,
            'end': str(curr),
            'count': 5000,
            'granularity': 300,
            'style': 'candles'
        })
        if 'candles' not in resp or not resp['candles']: break
        all_candles.extend(resp['candles'][::-1])
        curr = resp['candles'][0]['epoch'] - 1
        if len(all_candles) > (int(days) * 288 + 500): break
        await asyncio.sleep(0.1)

    await api.disconnect()
    df = pd.DataFrame(all_candles).drop_duplicates(subset=['epoch']).sort_values('epoch')
    os.makedirs('data', exist_ok=True)
    df.to_csv(cache_file, index=False)
    return df

@app.route('/run_backtest', methods=['POST'])
def run_bt():
    data = request.json
    days = data['days']
    symbol = data['symbol']

    # Run async data fetch in the bot loop
    future = asyncio.run_coroutine_threadsafe(get_bt_data(symbol, days), bot_loop)
    df = future.result()

    df = add_indicators(df)
    results = []
    strat_params = [
        (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
        (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
    ]

    for i, (a, c) in enumerate(strat_params):
        df_sig = ut_bot(df, a=a, c=c)
        trades = Backtester(df_sig).run()
        if not trades.empty:
            results.append({
                'name': f"Strategy {i+1}",
                'win_rate': trades['win'].mean(),
                'trades': len(trades),
                'max_losses': int(calculate_max_consecutive_losses(trades['win']))
            })

    return jsonify({'results': results})

def start_bot_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':
    bot_loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_bot_loop, args=(bot_loop,), daemon=True)
    t.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
