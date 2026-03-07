# Strategy Backtester Module

The Strategy Backtester is a core component of the Deriv UT Bot dashboard, allowing users to validate any of the 10 built-in strategies against historical market data with full Machine Learning filtering.

## 1. Overview

The backtester provides a "sandbox" environment where all strategies are executed simultaneously on a chosen dataset. This allows for a direct comparison of performance across different market conditions and volatility levels.

## 2. User Inputs

From the **Backtest** section in the UI, users can configure:
- **Days to Backtest:** The lookback period (e.g., 7 days, 30 days, 365 days).
- **Symbol:** The Volatility Index to test (R_10, R_25, R_50, R_75, R_100).
- **Initial Balance ($):** Your starting account capital for the simulation.
- **Risk per Trade (%):** The percentage of your current balance to stake on every trade.

## 3. Metrics and Results

The system processes the data and displays a comparison table with the following metrics:

| Metric | Description |
| :--- | :--- |
| **Strategy** | The name of the strategy (Strategy 1 to 10). |
| **Neural Accuracy** | The win rate achieved by the ML-filtered strategy. |
| **Max Consec. Losses** | The longest streak of consecutive losing trades observed. |
| **Trades** | The total number of signals confirmed by both UT Bot and the ML Filter. |
| **Final Balance** | The simulated account balance after all trades are completed. |
| **Projected PnL** | The net gain or loss in dollars. |

## 4. Financial Simulation Logic (Rise/Fall)

The backtester provides a realistic simulation of Deriv Rise/Fall options using the following logic:
- **Win Payout (+95%):** For every winning trade, the profit is calculated as 95% of the stake.
- **Loss (-100%):** For every losing trade, the entire stake is lost.
- **Dynamic Compounding:** The stake for each trade is calculated as a percentage of the **available balance at the time of the trade**. This simulates realistic account growth and decline.


## 5. How Machine Learning works in Backtesting

### Deep Training & Model Retention Architecture
The system uses a centralized `ModelManager` to ensure that backtesting and live trading are perfectly synchronized:
- **Pre-Trained Knowledge Base:** On startup, the bot automatically trains all 50 possible models (5 symbols × 10 strategies) using the **full 1-year historical archive** (~105,000 candles).
- **Faithful Simulation:** When you run a backtest in the UI, the system uses the **exact same trained model** that the live bot is using. This allows you to see precisely how the ML-enhanced strategy would have performed in your selected window.
- **State-Aware Backtesting:** If you trigger a backtest while the system is still in its startup training phase, the UI will clearly indicate which models are still "Training" or "Queued." In this case, results will show "baseline" performance until the model is ready.
- **Continuous Daily Retraining:** Every 24 hours (at 00:05 UTC), the bot fetches the previous day's closed data and **retrains every model**. This ensures the "Smart Coach" is always updated with the latest market shifts while retaining its long-term memory.

### Why no model files?
You won't see `.pkl` or `.model` files in the folder. This is intentional:
1.  **Adaptability:** The market changes constantly. A model trained on data from 6 months ago might be "stale." By training on-the-fly, the bot always stays current.
2.  **Memory-Only:** Training 100 mini-coaches takes only a few seconds. Keeping them in memory is faster and keeps the project folder clean.

## 6. Technical Implementation

### Data Retrieval and Caching
The backtester uses an intelligent, two-tier caching system for maximum efficiency:

1.  **UI Level Cache (Short-term):** For quick results, backtests requested via the UI use a **1-hour temporary cache** (`data/cache_[symbol]_[days]d.csv`).
2.  **Model Manager Cache (Long-term Archive):** The core 1-year historical data is stored in `data/[symbol]_5m_2y.csv`. Instead of downloading the full archive every day, the bot performs **Incremental Updates**:
    - It reads the CSV to see when the last candle was recorded.
    - It only fetches the specific candles that occurred between then and "now."
    - It merges the new data and removes the oldest candles to maintain a perfect 1-year sliding window.

### Processing Logic
1.  **Indicator Calculation:** The bot adds RSI, MACD, ADX, and other technical indicators to the historical data.
2.  **ML Training:** For each strategy, it first finds all potential "raw" signals. If there are more than 200, it trains the Random Forest model.
3.  **Filtering:** The model identifies and blocks potential losing trades.
4.  **Backtest Engine:** The `Backtester` class simulates the final trades using the **3-candle exit rule** (15-minute hold).
