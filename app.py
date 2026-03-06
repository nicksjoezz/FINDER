from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json, os, asyncio, threading, pandas as pd
from datetime import datetime, timedelta
from trading_bot import TradingBot
from model_manager import model_manager
from deriv_api import DerivAPI
from strategy_utils import ut_bot, Backtester, calculate_max_consecutive_losses, simulate_financials
from indicators import add_indicators

app = Flask(__name__)
socketio = SocketIO(app)
bot = TradingBot(socketio)
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"api_token": "381klIwm4Mr8BTT", "app_id": "99999", "symbol": "R_100", "strategy": "1", "trade_pc": 1, "is_live": False, "fetch_days": 730}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/get_config')
def get_configs(): return jsonify(load_config())

@app.route('/save_settings', methods=['POST'])
def save_configs():
    save_config(request.json)
    return jsonify({'status': 'success'})

@app.route('/toggle_bot', methods=['POST'])
def toggle_bot():
    if bot.is_running: asyncio.run_coroutine_threadsafe(bot.stop(), bot_loop)
    else:
        c = load_config()
        if not c.get('api_token'): return jsonify({'status': 'error'})
        asyncio.run_coroutine_threadsafe(bot.start(c), bot_loop)
    return jsonify({'status': 'success'})

@app.route('/get_system_status')
def get_sys_status(): return jsonify({'is_initial_training': model_manager.is_initial_training})

async def get_bt_data(symbol, days):
    fp = os.path.join('data', f"{symbol}_5m_2y.csv")
    ts = int((datetime.now() - timedelta(days=int(days))).timestamp())
    if os.path.exists(fp):
        df = pd.read_csv(fp)
        if not df.empty and df['epoch'].min() <= ts: return df[df['epoch'] >= ts]
    c = load_config()
    api = DerivAPI(app_id=c.get('app_id', '99999'))
    end, candles = int(datetime.now().timestamp()), []
    curr = end
    while curr > ts:
        r = await api.ticks_history({'ticks_history': symbol, 'end': str(curr), 'count': 5000, 'granularity': 300, 'style': 'candles'})
        if 'candles' not in r or not r['candles']: break
        candles.extend(r['candles'][::-1])
        curr = r['candles'][0]['epoch'] - 1
        if len(candles) > (int(days) * 288 + 500): break
    await api.disconnect()
    return pd.DataFrame(candles).drop_duplicates(subset=['epoch']).sort_values('epoch')

@app.route('/run_backtest', methods=['POST'])
def run_bt():
    d = request.json
    f = asyncio.run_coroutine_threadsafe(get_bt_data(d['symbol'], d['days']), bot_loop)
    df = add_indicators(f.result())
    if df.empty: return jsonify({'results': []})
    res = []
    params = [(1, 10), (2, 20), (3, 30), (1, 20), (2, 10), (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)]
    for i, (a, c) in enumerate(params):
        s_idx = i + 1
        df_sig = ut_bot(df, a=a, c=c)
        m_status = model_manager.get_model_status(d['symbol'], s_idx)
        if m_status == 'ready':
            df_f = model_manager.get_model(d['symbol'], s_idx).filter_signals(df_sig)
            tr = Backtester(df_f).run()
        else: tr = Backtester(df_sig).run()
        if not tr.empty:
            bal, prof = simulate_financials(tr, float(d.get('balance', 1000)), float(load_config().get('trade_pc', 1)))
            res.append({'name': f"Strategy {s_idx}", 'win_rate': tr['win'].mean(), 'trades': len(tr), 'max_losses': int(calculate_max_consecutive_losses(tr['win'])), 'ml_status': m_status, 'final_balance': bal, 'total_profit': prof})
    return jsonify({'results': res})

def start_bot_loop(loop):
    asyncio.set_event_loop(loop)
    loop.create_task(model_manager.daily_update_loop())
    loop.run_forever()

bot_loop = asyncio.new_event_loop()
model_manager.socketio = socketio
threading.Thread(target=start_bot_loop, args=(bot_loop,), daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
