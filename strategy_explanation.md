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
3.  **Pattern Recognition:** The model analyzes which base signals resulted in wins or losses based on the market conditions (RSI, ADX, MACD, etc.) at that time.

## 3. Training Data Volume & API Limitations

While the bot's optimization engine is designed to handle up to **2 years** of historical data (roughly **105,000 candles**), the actual data used for training is subject to **Deriv API limitations**:

- **Maximum Retrieval:** Deriv typically limits the amount of historical *candle* data accessible via the public API for synthetic indices. In practice, this often results in a rolling window of the last **4 to 6 months** (approx. **30,000 to 40,000 candles**) being available for the 5-minute timeframe.
- **The "Data Gap":** You may see "Training Data Volume: 35,000 candles" in the reports. This represents the **maximum available historical depth** provided by the API at the time of execution, rather than a lack of capability in the bot itself.
- **Minimum Requirement:** The bot still requires at least **200 historical trade signals** within this available window to successfully train the ML filter.

## 4. Decision Making in Live Trading

Once the bot is monitoring the live 5m timeframe, the execution logic for every new candle is as follows:

1.  **Check Fixed Signal:** Does the UT Bot generate a signal?
2.  **Consult ML Filter:** If a signal exists, the bot extracts the current market features and asks the **Machine Learning model**: *"Based on the available historical patterns, is this signal likely to be a winner?"*
3.  **Execution:**
    - If **ML predicts a WIN**: The trade is placed on the Deriv platform.
    - If **ML predicts a LOSS**: The signal is discarded.

## Summary

| Component | Nature | Purpose |
| :--- | :--- | :--- |
| **UT Bot Parameters** | **Fixed** | Defines the entry trigger logic. |
| **Technical Indicators** | **Dynamic** | Provides market context (volatility, momentum). |
| **ML Filter** | **Dynamic/Live Trained** | Filters out losing trades based on the *maximum available* recent history. |
