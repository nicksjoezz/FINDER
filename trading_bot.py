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
        self.config = {}
        self.balance = 0.0
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.api = None
        self.last_candle_epoch = 0
        self.ml_filters = {} # Cache ML filters per symbol/strategy

    def log(self, message):
        logging.info(message)
        self.socketio.emit('log', message)

    def update_status(self):
        self.socketio.emit('status_update', {
            'active': self.is_running,
            'balance': f"{self.balance:.2f}",
            'wins': self.wins,
            'losses': self.losses,
            'total_trades': self.total_trades
        })

    async def connect(self):
        try:
            self.api = DerivAPI(app_id=1089) # Or user provided app_id
            auth = await self.api.authorize(self.config['api_token'])
            self.balance = float(auth['authorize']['balance'])
            self.log(f"Connected to Deriv. Balance: {self.balance}")
            self.update_status()
            return True
        except Exception as e:
            self.log(f"Connection error: {e}")
            return False

    async def get_ml_filter(self, symbol, strategy_idx):
        # The ModelManager handles model lifecycle (training and retraining)
        ml = model_manager.get_model(symbol, strategy_idx)
        if ml:
            return ml

        self.log(f"Waiting for ML model for {symbol} Strategy {strategy_idx} to be ready...")
        return None

    async def start(self, config):
        self.config = config
        self.is_running = True
        if await self.connect():
            asyncio.create_task(self.main_loop())

    async def stop(self):
        self.is_running = False
        if self.api:
            await self.api.disconnect()
        self.log("Bot stopped.")
        self.update_status()

    async def main_loop(self):
        symbol = self.config['symbol']
        strategy_idx = int(self.config['strategy'])

        # Strategy mapping (simplified for demo)
        strat_params = [
            (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
            (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
        ]
        a, c = strat_params[strategy_idx-1]

        ml = await self.get_ml_filter(symbol, strategy_idx)

        self.log(f"Bot monitoring {symbol} with Strategy {strategy_idx}...")

        while self.is_running:
            try:
                # Fetch recent candles
                response = await self.api.ticks_history({
                    'ticks_history': symbol,
                    'end': 'latest',
                    'count': 300, # Enough for indicators
                    'granularity': 300,
                    'style': 'candles'
                })

                df = pd.DataFrame(response['candles'])
                current_candle = df.iloc[-1]

                if current_candle['epoch'] > self.last_candle_epoch:
                    # New candle formed
                    self.last_candle_epoch = current_candle['epoch']
                    self.log(f"New candle at {time.ctime(current_candle['epoch'])}")

                    # Always fetch the latest model from manager (handles daily retraining)
                    ml = await self.get_ml_filter(symbol, strategy_idx)

                    # Apply UT Bot
                    df_signals = ut_bot(df, a=a, c=c)
                    df_signals = add_indicators(df_signals)

                    # Apply ML Filter if available
                    if ml:
                        df_signals = ml.filter_signals(df_signals)

                    # Last completed candle is at -2
                    last_sig = df_signals.iloc[-2]

                    if last_sig['buy']:
                        await self.place_trade('CALL')
                    elif last_sig['sell']:
                        await self.place_trade('PUT')

                await asyncio.sleep(10) # Poll every 10s

            except Exception as e:
                self.log(f"Loop error: {e}")
                await asyncio.sleep(5)

    async def place_trade(self, side):
        amount = self.balance * (float(self.config['trade_pc']) / 100.0)
        amount = max(amount, 1.0) # Deriv min trade

        self.log(f"PLACING {side} TRADE - Amount: ${amount:.2f}")

        try:
            # Rise/Fall contract
            # 3 candles = 15 minutes = 900 seconds
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

            self.total_trades += 1
            self.log(f"Trade successfully placed: {proposal['buy']['contract_id']}")

            # In a real bot, we'd track the contract_id and update balance/wins/losses
            # For this dashboard demo, we'll simulate a result after 15m or just update balance periodically
            self.update_status()

        except Exception as e:
            self.log(f"Trade error: {e}")

import os
