import pandas as pd
import numpy as np
import ta
from sklearn.ensemble import RandomForestClassifier
from strategy_utils import ut_bot, Backtester
from indicators import add_indicators

class MLFilter:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.is_trained = False

    def prepare_features(self, df, indices):
        features = []
        for idx in indices:
            f = {
                'rsi': df['rsi'].iloc[idx],
                'macd_diff': df['macd_diff'].iloc[idx],
                'adx': df['adx'].iloc[idx],
                'bb_pband': (df['close'].iloc[idx] - df['bb_lband'].iloc[idx]) / (df['bb_hband'].iloc[idx] - df['bb_lband'].iloc[idx] + 1e-9),
                'ema_dist': (df['close'].iloc[idx] - df['ema_200'].iloc[idx]) / df['close'].iloc[idx]
            }
            features.append(list(f.values()))
        return np.array(features)

    def train(self, df, trades):
        df = add_indicators(df)

        # Match trades to candle indices
        # signal at i, entry at i+1
        epoch_to_idx = {epoch: idx for idx, epoch in enumerate(df['epoch'])}

        X_indices = []
        y = []

        for _, trade in trades.iterrows():
            entry_idx = epoch_to_idx.get(trade['entry_time'])
            if entry_idx is None or entry_idx == 0: continue
            signal_idx = entry_idx - 1

            X_indices.append(signal_idx)
            y.append(1 if trade['win'] else 0)

        if len(y) < 200: return False

        X = self.prepare_features(df, X_indices)
        self.model.fit(X, y)
        self.is_trained = True
        return True

    def filter_signals(self, df):
        if not self.is_trained: return df

        df = add_indicators(df).copy()

        # We only care about rows where there is a UT Bot signal
        buy_indices = df.index[df['buy']].tolist()
        sell_indices = df.index[df['sell']].tolist()

        if buy_indices:
            X_buy = self.prepare_features(df, buy_indices)
            preds_buy = self.model.predict(X_buy)
            # Only keep signals where ML predicts a Win
            for i, idx in enumerate(buy_indices):
                if preds_buy[i] == 0:
                    df.at[idx, 'buy'] = False

        if sell_indices:
            X_sell = self.prepare_features(df, sell_indices)
            preds_sell = self.model.predict(X_sell)
            for i, idx in enumerate(sell_indices):
                if preds_sell[i] == 0:
                    df.at[idx, 'sell'] = False

        return df
