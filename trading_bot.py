import asyncio
import pandas as pd
import numpy as np
import time
from deriv_api import DerivAPI
from strategy_utils import ut_bot
from indicators import add_indicators
from model_manager import model_manager
import logging

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

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S', time.gmtime())
        full_log = f"{timestamp} | {message}"
        logging.info(full_log)
        # Ensure it appears in terminal
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
            self.api = DerivAPI(app_id=app_id)
            self.log(f"Attempting API Authentication (App ID: {app_id})...")
            # Set a 30s timeout for auth
            auth = await asyncio.wait_for(self.api.authorize(self.config['api_token']), timeout=30)
            self.balance = float(auth['authorize']['balance'])
            self.log(f"AUTHENTICATED: Wallet balance is ${self.balance:.2f}")
            self.update_status()

            # Subscribe to balance updates and contract results
            asyncio.create_task(self.subscribe_to_updates())
            return True
        except Exception as e:
            self.log(f"CONNECTION FAILED: {e}")
            return False

    async def subscribe_to_updates(self):
        try:
            # Subscribe to proposal_open_contract to get results
            poc_sub = await self.api.subscribe({'proposal_open_contract': 1, 'subscribe': 1})
            poc_sub.subscribe(self.handle_contract_update)

            # Subscribe to balance
            bal_sub = await self.api.subscribe({'balance': 1, 'subscribe': 1})
            bal_sub.subscribe(self.handle_balance_update)
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

    async def get_ml_filter(self, symbol, strategy_idx):
        ml = model_manager.get_model(symbol, strategy_idx)
        return ml

    def reset_metrics(self):
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.log_history = []
        self.active_contracts = {}
        self.last_candle_epoch = 0

    async def start(self, config):
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

        if self.api:
            await self.api.disconnect()
            self.api = None

        self.log("Bot stopped.")
        self.update_status()

    async def main_loop(self):
        try:
            await self._main_loop_exec()
        except asyncio.CancelledError:
            self.log("Main loop task cancelled.")
        except Exception as e:
            self.log(f"Fatal main loop error: {e}")
        finally:
            self.is_running = False

    async def _main_loop_exec(self):
        symbol = self.config['symbol']
        strategy_idx = int(self.config['strategy'])

        strat_params = [
            (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
            (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
        ]
        a, c = strat_params[strategy_idx-1]

        self.log(f"Bot monitoring {symbol} with Strategy {strategy_idx} (a={a}, c={c})...")
        last_heartbeat = 0

        while self.is_running:
            try:
                now = time.time()
                # 60s Heartbeat log to confirm bot is active
                if now - last_heartbeat > 60:
                    self.log(f"System Heartbeat: Bot is actively monitoring {symbol}...")
                    last_heartbeat = now

                # Fetch recent candles (need at least 200 for indicators like EMA 200)
                # Set a 45s timeout for data fetch
                response = await asyncio.wait_for(self.api.ticks_history({
                    'ticks_history': symbol,
                    'end': 'latest',
                    'count': 500,
                    'granularity': 300,
                    'style': 'candles'
                }), timeout=45)

                if 'candles' not in response or not response['candles']:
                    self.log(f"Market Data Warning: No candles returned for {symbol}. Retrying...")
                    await asyncio.sleep(10)
                    continue

                df = pd.DataFrame(response['candles'])
                # We want signals from the last COMPLETED candle
                last_completed_candle = df.iloc[-2]

                if last_completed_candle['epoch'] > self.last_candle_epoch:
                    # New candle closed
                    self.last_candle_epoch = last_completed_candle['epoch']
                    candle_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.last_candle_epoch))
                    self.log(f"NEW CANDLE CLOSED: {candle_time}. Analyzing patterns...")

                    # Calculate Indicators on all but the current building candle
                    df_calc = df.iloc[:-1].copy()
                    df_calc = add_indicators(df_calc)

                    # UT Bot Signals
                    df_ut = ut_bot(df_calc, a=a, c=c)
                    raw_sig = df_ut.iloc[-1] # The signal for the last completed candle

                    buy_triggered = raw_sig['buy']
                    sell_triggered = raw_sig['sell']

                    if buy_triggered or sell_triggered:
                        side = 'BUY' if buy_triggered else 'SELL'
                        self.log(f"UT Bot {side} signal detected. Verifying with Neural Filter...")

                        # ML Filter verification
                        ml = await self.get_ml_filter(symbol, strategy_idx)
                        if ml:
                            self.log(f"Using Neural Filter v.{ml.trained_at}")
                            df_ml = ml.filter_signals(df_ut)
                            ml_sig = df_ml.iloc[-1]

                            if ml_sig['buy'] or ml_sig['sell']:
                                self.log(f"NEURAL FILTER: SIGNAL PASSED. Executing {side} trade.")
                                await self.place_trade('CALL' if buy_triggered else 'PUT')
                            else:
                                self.log(f"NEURAL FILTER: SIGNAL BLOCKED (Low probability patterns detected).")
                        else:
                            self.log(f"ML filter missing. Executing raw {side} trade.")
                            await self.place_trade('CALL' if buy_triggered else 'PUT')
                    else:
                        self.log(f"Analysis complete for candle {candle_time}: No UT Bot entries found.")

                await asyncio.sleep(10)

            except Exception as e:
                self.log(f"Main loop error: {e}")
                await asyncio.sleep(10)

    async def place_trade(self, side):
        try:
            # Check for existing active trades for this symbol to avoid double entry
            # In simple Rise/Fall 15m, maybe we only want one trade at a time
            if any(c['side'] == side for c in self.active_contracts.values()):
                self.log(f"Already have an active {side} trade. Skipping.")
                return

            stake_pc = float(self.config.get('trade_pc', 1))
            amount = self.balance * (stake_pc / 100.0)
            amount = round(max(amount, 0.35), 2) # Deriv min is 0.35 for some symbols

            self.log(f"PLACING {side} TRADE - Stake: ${amount:.2f}")

            # 3 candles = 15 minutes
            proposal = await self.api.buy({
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
            })

            if 'buy' in proposal:
                contract_id = proposal['buy']['contract_id']
                self.total_trades += 1
                self.active_contracts[contract_id] = {'side': side, 'stake': amount}
                self.log(f"SUCCESS: {side} trade placed! ID: {contract_id} | Stake: ${amount:.2f}")
            else:
                err = proposal.get('error', {}).get('message', 'Unknown error')
                self.log(f"EXECUTION ERROR: Failed to place {side} trade. Reason: {err}")

            self.update_status()

        except Exception as e:
            self.log(f"Trade placement error: {e}")
