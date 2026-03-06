import asyncio, pandas as pd, os, time, logging
from datetime import datetime, timedelta
from ml_filter import MLFilter
from strategy_utils import ut_bot, Backtester
from indicators import add_indicators

class ModelManager:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.models = {}
        self.is_initial_training = True
        self.symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']
        self.strat_params = [(1, 10), (2, 20), (3, 30), (1, 20), (2, 10), (3, 20), (1, 30), (2, 30), (3, 10), (1.5, 15)]
        self.data_dir, self.model_dir = 'data', 'models'
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)

    def log(self, message):
        logging.info(f"[ModelManager] {message}")
        if self.socketio: self.socketio.emit('log', f"[System] {message}")

    async def initialize_models(self):
        self.is_initial_training = True
        self.log("Loading models from disk...")
        for symbol in self.symbols:
            self.models[symbol] = {}
            for i in range(len(self.strat_params)):
                strat_idx = i + 1
                model_path = os.path.join(self.model_dir, f"{symbol}_strat_{strat_idx}.pkl")
                ml = MLFilter()
                if ml.load(model_path):
                    self.models[symbol][strat_idx] = {'model': ml, 'status': 'ready'}
                else:
                    self.models[symbol][strat_idx] = {'status': 'pending'}
        self.is_initial_training = False

    async def train_all_models(self):
        self.is_initial_training = True
        self.log("Updating data and retraining...")
        from fetch_data import update_symbol_data
        for symbol in self.symbols:
            await update_symbol_data(symbol, data_dir=self.data_dir)
            filepath = os.path.join(self.data_dir, f"{symbol}_5m_2y.csv")
            if not os.path.exists(filepath): continue
            df = add_indicators(pd.read_csv(filepath))
            for i, (a, c) in enumerate(self.strat_params):
                strat_idx = i + 1
                self.models[symbol][strat_idx]['status'] = 'training'
                raw_trades = Backtester(ut_bot(df, a=a, c=c)).run()
                if len(raw_trades) >= 200:
                    ml = MLFilter()
                    if ml.train(df, raw_trades):
                        ml.save(os.path.join(self.model_dir, f"{symbol}_strat_{strat_idx}.pkl"))
                        self.models[symbol][strat_idx] = {'model': ml, 'status': 'ready'}
                    else:
                        self.models[symbol][strat_idx]['status'] = 'ready' if self.get_model(symbol, strat_idx) else 'failed'
                else: self.models[symbol][strat_idx]['status'] = 'bypassed'
        self.is_initial_training = False

    def get_model_status(self, symbol, strategy_idx):
        return self.models.get(symbol, {}).get(int(strategy_idx), {}).get('status', 'pending')

    def get_model(self, symbol, strategy_idx):
        m = self.models.get(symbol, {}).get(int(strategy_idx), {})
        return m['model'] if m.get('status') == 'ready' else None

    async def daily_update_loop(self):
        await self.initialize_models()
        await self.train_all_models()
        while True:
            wait = ((datetime.utcnow() + timedelta(days=1)).replace(hour=0, minute=5, second=0) - datetime.utcnow()).total_seconds()
            await asyncio.sleep(wait)
            await self.train_all_models()

model_manager = ModelManager()
