import asyncio
import pandas as pd
import numpy as np
import time
import traceback
import logging
from datetime import datetime
from deriv_api import DerivAPI
from strategy_utils import ut_bot
from indicators import add_indicators
from model_manager import model_manager

class TradingBot:
    def __init__(self, socketio):
        self.socketio = socketio
        self.is_running = False
        self.main_task = None
        self.api = None
        self.config = {}

        # State metrics
        self.balance = 0.0
        self.wins = 0
        self.losses = 0
        self.total_trades = 0

        # Bot internals
        self.active_contracts = {} # cid -> {'side', 'stake'}
        self.log_history = []
        self.max_logs = 100
        self.candles_df = pd.DataFrame()
        self.subscriptions = []
        self.is_primed = False
        self.lock = asyncio.Lock()

        # Candle building state
        self.current_candle = None # {epoch, open, high, low, close}

    def log(self, message, level=logging.INFO):
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        full_log = f"{timestamp} | {message}"
        # Print to terminal
        print(f"[TradingBot] {full_log}", flush=True)
        # Emit to UI
        try:
            self.socketio.emit('log', message)
        except:
            pass
        # Store in history
        self.log_history.append(full_log)
        if len(self.log_history) > self.max_logs:
            self.log_history.pop(0)
        # Standard logger
        logging.log(level, f"[TradingBot] {message}")

    def update_status(self):
        try:
            self.socketio.emit('status_update', self.get_state())
        except:
            pass

    def get_state(self):
        return {
            'active': self.is_running,
            'balance': f"{self.balance:.2f}",
            'wins': self.wins,
            'losses': self.losses,
            'total_trades': self.total_trades,
            'config': self.config,
            'last_trained': model_manager.last_trained
        }

    async def start(self, config):
        async with self.lock:
            if self.is_running:
                self.log("Bot already running. Stopping previous instance...")
                await self._stop_internal()

            self.config = config
            self.reset_metrics()
            self.is_running = True
            self.log("Initializing high-fidelity trading engine...")
            self.main_task = asyncio.create_task(self.main_execution_loop())

    async def stop(self):
        async with self.lock:
            await self._stop_internal()
            self.log("Trading engine shut down.")
            self.update_status()

    async def _stop_internal(self):
        self.is_running = False
        if self.main_task:
            self.main_task.cancel()
            try:
                await self.main_task
            except asyncio.CancelledError:
                pass
            self.main_task = None
        await self.cleanup_api()

    def reset_metrics(self):
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.log_history = []
        self.active_contracts = {}
        self.candles_df = pd.DataFrame()
        self.is_primed = False
        self.current_candle = None

    async def cleanup_api(self):
        self.log("Cleaning up API resources...")
        for sub in self.subscriptions:
            try: sub.dispose()
            except: pass
        self.subscriptions = []

        if self.api:
            try:
                await asyncio.wait_for(self.api.disconnect(), timeout=10)
            except: pass
            self.api = None
        self.is_primed = False

    async def main_execution_loop(self):
        try:
            while self.is_running:
                if not self.api or not self.api.connected:
                    self.log("Establishing connection with Deriv...")
                    if not await self.establish_connection():
                        self.log("Connection failed. Retrying in 15 seconds...")
                        await asyncio.sleep(15)
                        continue

                # Keep-alive and connection monitoring
                try:
                    await asyncio.wait_for(self.api.ping({'ping': 1}), timeout=5)
                except:
                    self.log("Heartbeat loss. Re-establishing connection...")
                    await self.cleanup_api()
                    continue

                await asyncio.sleep(30)

        except asyncio.CancelledError:
            self.log("Main loop cancelled.")
        except Exception as e:
            err_msg = f"Fatal Loop Error: {type(e).__name__}: {e}"
            self.log(err_msg)
            print(traceback.format_exc(), flush=True)
        finally:
            self.is_running = False
            self.update_status()

    async def establish_connection(self):
        try:
            await self.cleanup_api()

            app_id = self.config.get('app_id', '62845')
            token = self.config.get('api_token')
            symbol = self.config['symbol']

            self.api = DerivAPI(app_id=app_id)
            self.log(f"Authenticating (App ID: {app_id})...")

            # 1. Authorize
            auth = await asyncio.wait_for(self.api.authorize(token), timeout=20)
            self.balance = float(auth['authorize']['balance'])
            self.log(f"Authenticated. Wallet Balance: ${self.balance:.2f}")

            # 2. Bootstrap History (300 candles)
            # Use raw send to avoid subscription manager issues for pure historical fetch
            self.log(f"Bootstrapping historical data for {symbol}...")
            history = await asyncio.wait_for(self.api.ticks_history({
                'ticks_history': symbol,
                'end': 'latest',
                'count': 300,
                'granularity': 300,
                'style': 'candles'
            }), timeout=30)

            if 'candles' in history:
                self.candles_df = pd.DataFrame(history['candles'])
                # Initialize current_candle from the last historical one
                last = history['candles'][-1]
                self.current_candle = {
                    'epoch': int(last['epoch']),
                    'open': float(last['open']),
                    'high': float(last['high']),
                    'low': float(last['low']),
                    'close': float(last['close'])
                }
                self.log(f"History Primed: {len(self.candles_df)} candles loaded.")
            else:
                self.log(f"Historical fetch failed: {history.get('error', {}).get('message', 'Unknown error')}")
                return False

            # 3. Core Subscriptions
            self.log("Activating live stream subscriptions...")

            bal_sub = await self.api.subscribe({'balance': 1})
            bal_sub.subscribe(self.handle_balance_update)
            self.subscriptions.append(bal_sub)

            poc_sub = await self.api.subscribe({'proposal_open_contract': 1})
            poc_sub.subscribe(self.handle_contract_update)
            self.subscriptions.append(poc_sub)

            # 4. Ticks Subscription for real-time candle building
            tick_sub = await self.api.subscribe({'ticks': symbol})
            tick_sub.subscribe(self.handle_tick_update)
            self.subscriptions.append(tick_sub)

            self.is_primed = True
            self.log(f"System Ready: monitoring {symbol} via real-time tick stream.")
            self.update_status()
            return True

        except Exception as e:
            self.log(f"Connection Setup Error: {e}")
            return False

    def handle_balance_update(self, data):
        if 'balance' in data:
            self.balance = float(data['balance']['balance'])
            self.update_status()

    def handle_contract_update(self, data):
        if 'proposal_open_contract' in data:
            contract = data['proposal_open_contract']
            if contract['is_sold']:
                status = contract['status']
                profit = float(contract['profit'])
                cid = contract['contract_id']
                if cid in self.active_contracts:
                    side = self.active_contracts[cid]['side']
                    if status == 'won':
                        self.wins += 1
                        self.log(f"PROFIT: {side} trade won! +${profit:.2f}")
                    else:
                        self.losses += 1
                        self.log(f"LOSS: {side} trade lost. -${abs(profit):.2f}")
                    del self.active_contracts[cid]
                    self.update_status()

    def handle_tick_update(self, data):
        if not self.is_primed or 'tick' not in data: return

        tick = data['tick']
        price = float(tick['quote'])
        epoch = int(tick['epoch'])

        # 5m boundary
        candle_start = (epoch // 300) * 300

        if not self.current_candle:
            self.current_candle = {'epoch': candle_start, 'open': price, 'high': price, 'low': price, 'close': price}
            return

        if candle_start == self.current_candle['epoch']:
            # Update current candle
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price
        elif candle_start > self.current_candle['epoch']:
            # CANDLE CLOSED
            # 1. Finalize the closed candle in our historical dataframe
            closed_candle = self.current_candle.copy()
            self.log(f"CANDLE COMPLETED: {datetime.utcfromtimestamp(closed_candle['epoch']).strftime('%H:%M:%S')}. Analyzing signals...")

            # Sync with candles_df (Update last or Append)
            if not self.candles_df.empty and self.candles_df.iloc[-1]['epoch'] == closed_candle['epoch']:
                for k in ['open','high','low','close']:
                    self.candles_df.iloc[-1, self.candles_df.columns.get_loc(k)] = closed_candle[k]
            else:
                self.candles_df = pd.concat([self.candles_df, pd.DataFrame([closed_candle])]).iloc[-400:].reset_index(drop=True)

            # 2. Trigger analysis
            asyncio.create_task(self.analyze_and_trade(self.candles_df.copy()))

            # 3. Start new candle
            self.current_candle = {'epoch': candle_start, 'open': price, 'high': price, 'low': price, 'close': price}

    async def analyze_and_trade(self, df):
        try:
            if not self.is_running: return

            symbol = self.config['symbol']
            strategy_idx = int(self.config['strategy'])
            params = [(1, 10), (2, 20), (3, 30), (1, 20), (2, 10), (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)]
            a, c = params[strategy_idx-1]

            if len(df) < 201:
                # self.log(f"History still building... ({len(df)}/200)")
                return

            # Apply indicators to history
            df_ind = add_indicators(df)
            df_ut = ut_bot(df_ind, a=a, c=c)

            # Signal on the last completed candle
            sig = df_ut.iloc[-1]
            buy_triggered = sig['buy']
            sell_triggered = sig['sell']

            if buy_triggered or sell_triggered:
                side = 'BUY' if buy_triggered else 'SELL'
                self.log(f"SIGNAL: {side} detected. Passing to Neural Filter...")

                ml = model_manager.get_model(symbol, strategy_idx)
                if ml:
                    df_ml = ml.filter_signals(df_ut)
                    ml_sig = df_ml.iloc[-1]
                    if ml_sig['buy'] or ml_sig['sell']:
                        self.log("NEURAL FILTER: PASSED. Executing market order.")
                        await self.place_trade('CALL' if buy_triggered else 'PUT')
                    else:
                        self.log("NEURAL FILTER: BLOCKED (Low probability score).")
                else:
                    self.log("Neural Filter offline. Executing raw signal.")
                    await self.place_trade('CALL' if buy_triggered else 'PUT')

        except Exception as e:
            self.log(f"Analysis process failed: {e}")
            print(traceback.format_exc(), flush=True)

    async def place_trade(self, side):
        try:
            # Overlap protection
            if any(c['side'] == side for c in self.active_contracts.values()):
                self.log(f"Skipping overlapping {side} trade.")
                return

            stake_pc = float(self.config.get('trade_pc', 1))
            amount = round(max(self.balance * (stake_pc / 100.0), 0.35), 2)

            self.log(f"PLACING {side} ORDER - Stake: ${amount:.2f}")

            # Duration 15m (3 candles)
            resp = await asyncio.wait_for(self.api.buy({
                "buy": 1,
                "price": amount,
                "parameters": {
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": "CALL" if side == "CALL" else "PUT",
                    "currency": "USD",
                    "duration": 15,
                    "duration_unit": "m",
                    "symbol": self.config['symbol']
                }
            }), timeout=30)

            if 'buy' in resp:
                cid = resp['buy']['contract_id']
                self.total_trades += 1
                self.active_contracts[cid] = {'side': side, 'stake': amount}
                self.log(f"ORDER SUCCESS: {side} ID {cid} is now active.")
            else:
                err = resp.get('error', {}).get('message', 'Unknown API Error')
                self.log(f"ORDER FAILED: {err}")

            self.update_status()
        except Exception as e:
            self.log(f"Execution failed: {e}")
