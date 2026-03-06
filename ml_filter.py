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
        self.feature_cols = ['rsi', 'macd_diff', 'adx', 'bb_pct', 'ema_dist']

    def prepare_features(self, df, indices):
        # Ensure indices are valid
        valid_indices = [idx for idx in indices if 0 <= idx < len(df)]
        if not valid_indices:
            return np.zeros((0, len(self.feature_cols)))

        # Pre-calculate features to avoid repeated iloc in loop if possible,
        # but for simplicity and given small number of features, we'll do it carefully.

        # Calculate bb_pct and ema_dist if not in df
        if 'bb_pct' not in df.columns:
            df = df.copy()
            df['bb_pct'] = (df['close'] - df['bb_lband']) / (df['bb_hband'] - df['bb_lband'] + 1e-9)
            df['ema_dist'] = (df['close'] - df['ema_200']) / df['close']

        feature_data = df.iloc[valid_indices][['rsi', 'macd_diff', 'adx', 'bb_pct', 'ema_dist']]
        # Fill NaNs with 0 or handle them
        feature_data = feature_data.fillna(0)

        return feature_data.values

    def train(self, df, trades):
        if trades.empty:
            return False

        # Ensure indicators are present
        if 'bb_pct' not in df.columns:
            df = df.copy()
            df['bb_pct'] = (df['close'] - df['bb_lband']) / (df['bb_hband'] - df['bb_lband'] + 1e-9)
            df['ema_dist'] = (df['close'] - df['ema_200']) / df['close']

        epoch_to_idx = {epoch: idx for idx, epoch in enumerate(df['epoch'])}
        X_indices, y = [], []

        for _, trade in trades.iterrows():
            entry_epoch = trade['entry_time']
            if entry_epoch not in epoch_to_idx: continue
            entry_idx = epoch_to_idx[entry_epoch]

            # We want features from the candle BEFORE the entry (the signal candle)
            signal_idx = entry_idx - 1
            if signal_idx < 0: continue

            # Check if features are NaN at this index
            if pd.isna(df.iloc[signal_idx][['rsi', 'macd_diff', 'adx', 'bb_pct', 'ema_dist']]).any():
                continue

            X_indices.append(signal_idx)
            y.append(1 if trade['win'] else 0)

        if len(y) < 200:
            return False

        X = self.prepare_features(df, X_indices)
        self.model.fit(X, y)
        self.is_trained = True
        return True

    def filter_signals(self, df):
        if not self.is_trained: return df
        df = df.copy()

        # Pre-calculate needed features for filtering
        if 'bb_pct' not in df.columns:
            df['bb_pct'] = (df['close'] - df['bb_lband']) / (df['bb_hband'] - df['bb_lband'] + 1e-9)
            df['ema_dist'] = (df['close'] - df['ema_200']) / df['close']

        for side in ['buy', 'sell']:
            indices = df.index[df[side]].tolist()
            if not indices: continue

            # We filter based on the candle where the signal occurred
            features = self.prepare_features(df, indices)
            if len(features) == 0: continue

            preds = self.model.predict(features)
            for i, idx in enumerate(indices):
                # If prediction is 0 (loss), block the signal
                if preds[i] == 0:
                    df.at[idx, side] = False
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
