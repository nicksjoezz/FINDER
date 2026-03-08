import asyncio
import pandas as pd
import numpy as np
import time
import traceback
import logging
from deriv_api import DerivAPI
from strategy_utils import ut_bot
from indicators import add_indicators
from model_manager import model_manager

class TradingBot:
    def __init__(self, socketio):
        self.socketio = socketio
        self.is_running = False
        self.main_task = None
        self.config = {}
        self.balance = 0.0
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.api = None
        self.last_candle_epoch = 0
        self.active_contracts = {} # contract_id -> {'side', 'entry_time', 'stake'}
        self.log_history = []
        self.max_logs = 100
        self.candles_df = pd.DataFrame()
        self.subscriptions = []

    def log(self, message, level=logging.INFO):
        timestamp = time.strftime('%H:%M:%S', time.gmtime())
        full_log = f"{timestamp} | {message}"
        logging.log(level, f"[TradingBot] {full_log}")
        if level >= logging.INFO:
            print(f"[TradingBot] {full_log}", flush=True)
        self.log_history.append(full_log)
        if len(self.log_history) > self.max_logs:
            self.log_history.pop(0)
        self.socketio.emit('log', message)

    def update_status(self):
        self.socketio.emit('status_update', self.get_state())

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

    async def connect(self):
        try:
            app_id = self.config.get('app_id', '62845')
            if self.api:
                await self.cleanup_api()

            self.api = DerivAPI(app_id=app_id)
            self.log(f"Attempting API Authentication (App ID: {app_id})...")
            auth = await asyncio.wait_for(self.api.authorize(self.config['api_token']), timeout=30)
            self.balance = float(auth['authorize']['balance'])
            self.log(f"AUTHENTICATED: Wallet balance is ${self.balance:.2f}")
            self.update_status()

            await self.start_subscriptions()
            return True
        except Exception as e:
            self.log(f"CONNECTION FAILED: {e}")
            return False

    async def cleanup_api(self):
        self.log("Cleaning up existing API connection and subscriptions...")
        for sub in self.subscriptions:
            try:
                sub.dispose()
            except:
                pass
        self.subscriptions = []

        if self.api:
            try:
                # Disconnect can sometimes hang if tasks are pending
                await asyncio.wait_for(self.api.disconnect(), timeout=10)
            except:
                pass
            self.api = None

    async def start_subscriptions(self):
        try:
            # 1. Balance Subscription
            bal_sub = await self.api.subscribe({'balance': 1, 'subscribe': 1})
            bal_sub.subscribe(self.handle_balance_update)
            self.subscriptions.append(bal_sub)

            # 2. Contract Updates Subscription
            poc_sub = await self.api.subscribe({'proposal_open_contract': 1, 'subscribe': 1})
            poc_sub.subscribe(self.handle_contract_update)
            self.subscriptions.append(poc_sub)

            # 3. OHLC Subscription
            symbol = self.config['symbol']
            ohlc_sub = await self.api.subscribe({'ohlc': symbol, 'subscribe': 1, 'granularity': 300})
            ohlc_sub.subscribe(self.handle_ohlc_update)
            self.subscriptions.append(ohlc_sub)

            self.log(f"Real-time subscriptions active for {symbol}.")
        except Exception as e:
            self.log(f"Subscription error: {e}")

    def handle_balance_update(self, data):
        if 'balance' in data:
            self.balance = float(data['balance']['balance'])
            self.update_status()

    def handle_contract_update(self, data):
        if 'proposal_open_contract' in data:
            contract = data['proposal_open_contract']
            if contract['is_sold']:
                status = contract['status'] # won, lost
                profit = float(contract['profit'])
                contract_id = contract['contract_id']

                if contract_id in self.active_contracts:
                    side = self.active_contracts[contract_id]['side']
                    if status == 'won':
                        self.wins += 1
                        self.log(f"PROFIT: {side} trade won! +${profit:.2f}")
                    else:
                        self.losses += 1
                        self.log(f"LOSS: {side} trade lost. -${abs(profit):.2f}")

                    del self.active_contracts[contract_id]
                    self.update_status()

    def handle_ohlc_update(self, data):
        if 'ohlc' not in data: return
        ohlc = data['ohlc']
        epoch = int(ohlc['open_time'])

        new_candle = {
            'epoch': epoch,
            'open': float(ohlc['open']),
            'high': float(ohlc['high']),
            'low': float(ohlc['low']),
            'close': float(ohlc['close'])
        }

        if self.candles_df.empty:
            # Should be bootstrapped by main_loop first, but safety check
            self.candles_df = pd.DataFrame([new_candle])
            return

        # Update last candle or append new one
        last_idx = self.candles_df.index[-1]
        if epoch == self.candles_df.at[last_idx, 'epoch']:
            # Still same candle, update it
            for key in ['open', 'high', 'low', 'close']:
                self.candles_df.at[last_idx, key] = new_candle[key]
        elif epoch > self.candles_df.at[last_idx, 'epoch']:
            # New candle started! The PREVIOUS one is now closed.
            closed_epoch = self.candles_df.at[last_idx, 'epoch']
            candle_time = time.strftime('%H:%M:%S', time.gmtime(closed_epoch))
            self.log(f"CANDLE CLOSED: {candle_time}. Triggering analysis...")

            # Append the new building candle
            self.candles_df = pd.concat([self.candles_df, pd.DataFrame([new_candle])]).iloc[-400:].reset_index(drop=True)

            # Trigger analysis as a background task
            asyncio.create_task(self.analyze_and_trade())

    async def analyze_and_trade(self):
        try:
            symbol = self.config['symbol']
            strategy_idx = int(self.config['strategy'])
            strat_params = [
                (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
                (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
            ]
            a, c = strat_params[strategy_idx-1]

            # We analyze the candles EXCEPT the very last one (which is currently building)
            df_analysis = self.candles_df.iloc[:-1].copy()
            if len(df_analysis) < 200:
                self.log(f"Insufficient history for analysis: {len(df_analysis)}/200")
                return

            df_analysis = add_indicators(df_analysis)
            df_ut = ut_bot(df_analysis, a=a, c=c)
            raw_sig = df_ut.iloc[-1]

            buy_triggered = raw_sig['buy']
            sell_triggered = raw_sig['sell']

            if buy_triggered or sell_triggered:
                side = 'BUY' if buy_triggered else 'SELL'
                self.log(f"SIGNAL: UT Bot {side} detected. Checking Neural Filter...")

                ml = await self.get_ml_filter(symbol, strategy_idx)
                if ml:
                    df_ml = ml.filter_signals(df_ut)
                    ml_sig = df_ml.iloc[-1]
                    if ml_sig['buy'] or ml_sig['sell']:
                        self.log(f"Neural Filter v.{ml.trained_at} PASSED. Placing trade.")
                        await self.place_trade('CALL' if buy_triggered else 'PUT')
                    else:
                        self.log(f"Neural Filter BLOCKED {side} signal.")
                else:
                    self.log(f"Neural Filter missing. Executing raw {side} trade.")
                    await self.place_trade('CALL' if buy_triggered else 'PUT')
            else:
                # Heartbeat of analysis to confirm it ran
                # self.log(f"Analysis complete: No entry signals found.", level=logging.DEBUG)
                pass

        except Exception as e:
            self.log(f"Critical error in analysis task: {e}")
            print(traceback.format_exc())

    async def get_ml_filter(self, symbol, strategy_idx):
        return model_manager.get_model(symbol, strategy_idx)

    def reset_metrics(self):
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.log_history = []
        self.active_contracts = {}
        self.last_candle_epoch = 0
        self.candles_df = pd.DataFrame()

    async def start(self, config):
        self.log("Initializing bot for live trading...")
        self.reset_metrics()
        self.config = config
        self.is_running = True
        if await self.connect():
            self.main_task = asyncio.create_task(self.main_loop())
        else:
            self.is_running = False
            self.update_status()

    async def stop(self):
        self.is_running = False
        if self.main_task:
            self.main_task.cancel()
            try:
                await self.main_task
            except asyncio.CancelledError:
                pass
            self.main_task = None

        await self.cleanup_api()
        self.log("Bot halted.")
        self.update_status()

    async def main_loop(self):
        try:
            symbol = self.config['symbol']
            # Bootstrap historical data
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
                self.log(f"Loaded {len(self.candles_df)} historical candles.")
            else:
                self.log("Failed to bootstrap history. Monitoring subscriptions only.")

            last_heartbeat = 0
            while self.is_running:
                # Connection health check
                try:
                    await asyncio.wait_for(self.api.ping({'ping': 1}), timeout=5)
                except:
                    self.log("WebSocket Ping failed. Attempting recovery...")
                    if not await self.connect():
                        await asyncio.sleep(10)
                        continue

                now = time.time()
                if now - last_heartbeat > 60:
                    self.log(f"Bot Active: Real-time stream for {symbol} is healthy.")
                    last_heartbeat = now

                await asyncio.sleep(10)

        except asyncio.CancelledError:
            self.log("Background monitoring task terminated.")
        except Exception as e:
            self.log(f"Main loop encountered a fatal error: {e}")
            print(traceback.format_exc())
        finally:
            self.is_running = False

    async def place_trade(self, side):
        try:
            # Check for existing active trades for this symbol
            if any(c['side'] == side for c in self.active_contracts.values()):
                self.log(f"Active {side} trade already exists. Avoiding duplicate entry.")
                return

            stake_pc = float(self.config.get('trade_pc', 1))
            amount = self.balance * (stake_pc / 100.0)
            amount = round(max(amount, 0.35), 2)

            self.log(f"EXECUTION: {side} trade triggered. Stake: ${amount:.2f}")

            # 3 candles = 15 minutes
            proposal = await asyncio.wait_for(self.api.buy({
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

            if 'buy' in proposal:
                contract_id = proposal['buy']['contract_id']
                self.total_trades += 1
                self.active_contracts[contract_id] = {'side': side, 'stake': amount}
                self.log(f"ORDER PLACED: {side} | ID: {contract_id}")
            else:
                err = proposal.get('error', {}).get('message', 'Unknown execution error')
                self.log(f"ORDER FAILED: {err}")

            self.update_status()

        except Exception as e:
            self.log(f"Trade execution error: {e}")
