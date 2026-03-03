# Strategy Implementation: Fixed Parameters vs. ML

This document explains how the strategies in this bot operate during live trading. The bot uses a **hybrid approach** that combines fixed technical indicator parameters with dynamic Machine Learning filtering.

## 1. The Core Strategy (Fixed Parameters)

Each of the 10 strategies selected in the dashboard has a set of **fixed parameters** for the underlying technical indicators. Specifically, they use the **UT Bot Alerts** logic with predetermined sensitivity (`a`) and ATR periods (`c`).

For example:
- **Strategy 1:** Sensitivity = 1, ATR = 10
- **Strategy 10:** Sensitivity = 1.5, ATR = 15

These fixed parameters provide the "base" signals for potential trades.

## 2. The Live ML Filter (Dynamic)

When you start the bot for a specific symbol (e.g., Volatility 100) and strategy, the bot does not just rely on the fixed signals. Instead, it performs the following steps **on startup**:

1.  **Symbol-Specific Training:** The bot fetches recent historical data for the selected symbol.
2.  **Model Fitting:** It trains a **Random Forest Classifier** specifically for that symbol and strategy.
3.  **Pattern Recognition:** The model analyzes which base signals (from the fixed parameters) resulted in wins or losses based on the market conditions (RSI, ADX, MACD, etc.) at that time.

## 3. Training Data Volume

To ensure the Machine Learning model is robust and has seen enough market cycles, the following data volume is used:
- **Target History:** Approximately **2 years** of historical data.
- **Candle Count:** Roughly **105,000 candles** per symbol (on the 5-minute timeframe).
- **Minimum Requirement:** The bot requires at least **200 historical trade signals** from the selected UT Bot configuration to successfully train the ML filter. If insufficient data is available for a specific symbol/strategy pair, the ML filter will be disabled to avoid unreliable predictions.

## 4. Decision Making in Live Trading

Once the bot is monitoring the live 5m timeframe, the execution logic for every new candle is as follows:

1.  **Check Fixed Signal:** Does the UT Bot (with its fixed `a` and `c` parameters) generate a Buy or Sell signal?
2.  **Consult ML Filter:** If a fixed signal exists, the bot extracts the current market features (RSI, ADX, MACD, etc.) and asks the **Machine Learning model**: *"Based on what you learned from recent history, is this signal likely to be a winner?"*
3.  **Execution:**
    - If **ML predicts a WIN**: The trade is placed on the Deriv platform.
    - If **ML predicts a LOSS**: The signal is discarded, and no trade is placed.

## Summary

| Component | Nature | Purpose |
| :--- | :--- | :--- |
| **UT Bot Parameters** | **Fixed** | Defines the entry trigger logic. |
| **Technical Indicators** | **Dynamic** | Provides market context (volatility, momentum). |
| **ML Filter** | **Dynamic/Live Trained** | Acts as a smart "gatekeeper" to filter out losing trades. |

**The result is a strategy that is anchored in proven technical logic but adapts its execution based on the most recent market behavior of the specific index being traded.**
