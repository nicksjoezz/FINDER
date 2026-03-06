import pandas as pd
import numpy as np
import ta
from sklearn.ensemble import RandomForestClassifier
from strategy_utils import ut_bot, Backtester
from indicators import add_indicators
import joblib
import os

class MLFilter:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.is_trained = False

    def prepare_features(self, df, indices):
        features = []
        for idx in indices:
            if idx >= len(df):
                features.append([0, 0, 0, 0, 0])
                continue
            f = [
                df['rsi'].iloc[idx],
                df['macd_diff'].iloc[idx],
                df['adx'].iloc[idx],
                (df['close'].iloc[idx] - df['bb_lband'].iloc[idx]) / (df['bb_hband'].iloc[idx] - df['bb_lband'].iloc[idx] + 1e-9),
                (df['close'].iloc[idx] - df['ema_200'].iloc[idx]) / df['close'].iloc[idx]
            ]
            features.append(f)
        return np.array(features)

    def train(self, df, trades):
        epoch_to_idx = {epoch: idx for idx, epoch in enumerate(df['epoch'])}
        X_indices, y = [], []
        for _, trade in trades.iterrows():
            entry_epoch = trade['entry_time']
            if entry_epoch not in epoch_to_idx: continue
            entry_idx = epoch_to_idx[entry_epoch]
            if entry_idx == 0: continue
            X_indices.append(entry_idx - 1)
            y.append(1 if trade['win'] else 0)
        if len(y) < 200: return False
        X = self.prepare_features(df, X_indices)
        self.model.fit(X, y)
        self.is_trained = True
        return True

    def filter_signals(self, df):
        if not self.is_trained: return df
        df = df.copy()
        for side in ['buy', 'sell']:
            indices = df.index[df[side]].tolist()
            if indices:
                preds = self.model.predict(self.prepare_features(df, indices))
                for i, idx in enumerate(indices):
                    if preds[i] == 0: df.at[idx, side] = False
        return df

    def save(self, filepath): joblib.dump(self.model, filepath)
    def load(self, filepath):
        if os.path.exists(filepath):
            try:
                self.model = joblib.load(filepath)
                self.is_trained = True
                return True
            except: pass
        return False
