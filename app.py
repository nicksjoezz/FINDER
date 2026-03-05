from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json
import os
import asyncio
import threading
from trading_bot import TradingBot
from model_manager import model_manager
import pandas as pd
from datetime import datetime, timedelta
from deriv_api import DerivAPI
from strategy_utils import ut_bot, Backtester, calculate_max_consecutive_losses, simulate_financials
from indicators import add_indicators

app = Flask(__name__)
socketio = SocketIO(app)
bot = TradingBot(socketio)

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "api_token": "381klIwm4Mr8BTT",
        "app_id": "62845",
        "symbol": "R_100",
        "strategy": "1",
        "trade_pc": 1,
        "is_live": false
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_config')
def get_configs():
    return jsonify(load_config())

@app.route('/save_settings', methods=['POST'])
def save_configs():
    config = request.json
    save_config(config)
    return jsonify({'status': 'success'})

@app.route('/toggle_bot', methods=['POST'])
def toggle_bot():
    if bot.is_running:
        asyncio.run_coroutine_threadsafe(bot.stop(), bot_loop)
    else:
        config = load_config()
        if not config.get('api_token'):
            return jsonify({'status': 'error', 'message': 'Missing API Token'})
        asyncio.run_coroutine_threadsafe(bot.start(config), bot_loop)
    return jsonify({'status': 'success'})

@app.route('/get_system_status')
def get_sys_status():
    return jsonify({
        'is_initial_training': model_manager.is_initial_training
    })

async def get_bt_data(symbol, days):
    # Caching logic
    cache_file = f"data/cache_{symbol}_{days}d.csv"
    if os.path.exists(cache_file):
        # Check if cache is fresh (less than 1 hour old)
        if (datetime.now().timestamp() - os.path.getmtime(cache_file)) < 3600:
            return pd.read_csv(cache_file)

    config = load_config()
    app_id = config.get('app_id', '62845')
    api = DerivAPI(app_id=app_id)
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
    initial_balance = float(data.get('balance', 1000))
    risk_pc = float(data.get('risk', 1))

    # 1. Fetch the "Test Period" data (the window the user wants to see)
    future = asyncio.run_coroutine_threadsafe(get_bt_data(symbol, days), bot_loop)
    df_test = future.result()
    df_test = add_indicators(df_test)

    results = []
    strat_params = [
        (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
        (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
    ]

    for i, (a, c) in enumerate(strat_params):
        strat_idx = i + 1
        # A. Signals for the Test Period
        df_sig_test = ut_bot(df_test, a=a, c=c)
        raw_trades_test = Backtester(df_sig_test).run()

        final_trades = pd.DataFrame()
        ml_status = model_manager.get_model_status(symbol, strat_idx)

        if ml_status == 'ready':
            ml = model_manager.get_model(symbol, strat_idx)
            df_filtered_test = ml.filter_signals(df_sig_test)
            final_trades = Backtester(df_filtered_test).run()
        else:
            final_trades = raw_trades_test

        if not final_trades.empty:
            final_balance, total_profit = simulate_financials(final_trades, initial_balance, risk_pc)

            results.append({
                'name': f"Strategy {i+1}",
                'win_rate': final_trades['win'].mean(),
                'trades': len(final_trades),
                'max_losses': int(calculate_max_consecutive_losses(final_trades['win'])),
                'ml_status': ml_status,
                'final_balance': final_balance,
                'total_profit': total_profit
            })

    return jsonify({'results': results})

def start_bot_loop(loop):
    asyncio.set_event_loop(loop)
    # 1. Start Initial Model Training
    loop.create_task(model_manager.train_all_models())
    # 2. Start Daily Retraining Cycle
    loop.create_task(model_manager.daily_update_loop())
    loop.run_forever()

# Initialize bot loop and background tasks globally so they start under WSGI/Gunicorn
bot_loop = asyncio.new_event_loop()
model_manager.socketio = socketio # Inject socketio for logs
t = threading.Thread(target=start_bot_loop, args=(bot_loop,), daemon=True)
t.start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
