import asyncio
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from ml_filter import MLFilter
from strategy_utils import ut_bot, Backtester
from indicators import add_indicators
import logging

class ModelManager:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.models = {} # {symbol: {strategy_idx: {'model': ml, 'last_trained': timestamp, 'status': str}}}
        self.is_initial_training = True
        self.symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']
        self.strat_params = [
            (1, 10), (2, 20), (3, 30), (1, 20), (2, 10),
            (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)
        ]
        self.data_dir = 'data'
        os.makedirs(self.data_dir, exist_ok=True)

    def log(self, message):
        logging.info(f"[ModelManager] {message}")
        if self.socketio:
            self.socketio.emit('log', f"[System] {message}")

    async def train_all_models(self):
        self.is_initial_training = True
        self.log("Starting model training phase for all symbols and strategies...")

        # 0. Ensure data is available
        from fetch_data import update_symbol_data
        for symbol in self.symbols:
            self.log(f"Checking data continuity for {symbol}...")
            await update_symbol_data(symbol, data_dir=self.data_dir)

        for symbol in self.symbols:
            filepath = os.path.join(self.data_dir, f"{symbol}_5m_2y.csv")
            if not os.path.exists(filepath):
                self.log(f"Data file for {symbol} still missing. Skipping...")
                continue

            df = pd.read_csv(filepath)
            df = add_indicators(df)

            if symbol not in self.models:
                self.models[symbol] = {}

            for i, (a, c) in enumerate(self.strat_params):
                strat_idx = i + 1
                self.models[symbol][strat_idx] = {'status': 'training'}
                self.log(f"Processing {symbol} Strategy {strat_idx} (a={a}, c={c})...")

                df_raw = ut_bot(df, a=a, c=c)
                raw_trades = Backtester(df_raw).run()

                if len(raw_trades) >= 200:
                    ml = MLFilter()
                    if ml.train(df, raw_trades):
                        self.models[symbol][strat_idx] = {
                            'model': ml,
                            'last_trained': time.time(),
                            'status': 'ready'
                        }
                        self.log(f"Successfully trained {symbol} Strategy {strat_idx}")
                    else:
                        self.models[symbol][strat_idx] = {'status': 'failed'}
                        self.log(f"Failed to train {symbol} Strategy {strat_idx}")
                else:
                    self.models[symbol][strat_idx] = {'status': 'bypassed'}
                    self.log(f"Bypassed {symbol} Strategy {strat_idx} (Insufficient signals: {len(raw_trades)})")

        self.is_initial_training = False
        self.log("All models processed and ready.")

    def get_model_status(self, symbol, strategy_idx):
        symbol_models = self.models.get(symbol, {})
        data = symbol_models.get(int(strategy_idx))
        if data:
            return data.get('status', 'pending')
        return 'pending'

    def get_model(self, symbol, strategy_idx):
        symbol_models = self.models.get(symbol, {})
        model_data = symbol_models.get(int(strategy_idx))
        if model_data:
            return model_data['model']
        return None

    async def daily_update_loop(self):
        while True:
            # Wait until 00:05 UTC to get the previous closed day
            now = datetime.utcnow()
            next_run = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            wait_seconds = (next_run - now).total_seconds()

            self.log(f"Next retraining scheduled in {wait_seconds/3600:.1f} hours.")
            await asyncio.sleep(wait_seconds)

            self.log("Starting daily retraining with updated data...")

            # 1. Incrementally update data files
            from fetch_data import update_symbol_data

            for symbol in self.symbols:
                self.log(f"Checking for updates for {symbol}...")
                await update_symbol_data(symbol, data_dir=self.data_dir)

            # 2. Retrain all 50 models
            await self.train_all_models()
            self.log("Daily retraining cycle finished.")

# Global instance
model_manager = ModelManager()
