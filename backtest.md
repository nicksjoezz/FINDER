# Strategy Backtester Module

The Strategy Backtester is a core component of the Deriv UT Bot dashboard, allowing users to validate any of the 10 built-in strategies against historical market data with full Machine Learning filtering.

## 1. Overview

The backtester provides a "sandbox" environment where all strategies are executed simultaneously on a chosen dataset. This allows for a direct comparison of performance across different market conditions and volatility levels.

## 2. User Inputs

From the **Backtest** section in the UI, users can configure:
- **Days to Backtest:** The lookback period (e.g., 7 days, 30 days, 365 days).
- **Symbol:** The Volatility Index to test (R_10, R_25, R_50, R_75, R_100).

## 3. Metrics and Results

The system processes the data and displays a comparison table with the following metrics:

| Metric | Description |
| :--- | :--- |
| **Strategy** | The name of the strategy (Strategy 1 to 10). |
| **ML Filter** | Shows if the Random Forest filter was active. It requires at least **200 historical signals** to train successfully. |
| **Win Rate** | The percentage of trades that resulted in a profit. |
| **Trades** | The total number of signals confirmed by both UT Bot and the ML Filter. |
| **Max Consec. Losses** | The longest "losing streak" observed during the period. |

## 4. How Machine Learning works in Backtesting

### Dynamic Training
The bot does **not** use a static, pre-saved model file. Instead, it handles everything in the background:
- **Every time you run a backtest**, the bot creates a fresh **ML Coach** (Random Forest Classifier).
- It "trains" this coach using the specific historical data you requested.
- This ensures that the coach's "cheat sheet" is perfectly tailored to the most recent patterns in the market you are studying.

### Why no model files?
You won't see `.pkl` or `.model` files in the folder. This is intentional:
1.  **Adaptability:** The market changes constantly. A model trained on data from 6 months ago might be "stale." By training on-the-fly, the bot always stays current.
2.  **Memory-Only:** Training 100 mini-coaches takes only a few seconds. Keeping them in memory is faster and keeps the project folder clean.

## 5. Technical Implementation

### Data Retrieval and Caching
To ensure speed and efficiency, the backtester uses a **1-hour caching mechanism**:
- When a backtest is requested, the bot checks `data/cache_[symbol]_[days]d.csv`.
- If the file exists and is less than 1 hour old, it is reused.
- Otherwise, the bot fetches fresh 5-minute candles from the Deriv API.

### Processing Logic
1.  **Indicator Calculation:** The bot adds RSI, MACD, ADX, and other technical indicators to the historical data.
2.  **ML Training:** For each strategy, it first finds all potential "raw" signals. If there are more than 200, it trains the Random Forest model.
3.  **Filtering:** The model identifies and blocks potential losing trades.
4.  **Backtest Engine:** The `Backtester` class simulates the final trades using the **3-candle exit rule** (15-minute hold).
