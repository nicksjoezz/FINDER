# Strategy Backtester Module

The Strategy Backtester is a core component of the Deriv UT Bot dashboard, allowing users to validate any of the 10 built-in strategies against historical market data before committing to live trading.

## 1. Overview

The backtester provides a "sandbox" environment where all strategies are executed simultaneously on a chosen dataset. This allows for a direct comparison of performance across different market conditions and volatility levels.

## 2. User Inputs

From the **Backtest** section in the UI, users can configure:
- **Days to Backtest:** The lookback period (e.g., 7 days, 30 days).
- **Symbol:** The Volatility Index to test (R_10, R_25, R_50, R_75, R_100).

## 3. Metrics and Results

Once the "Run Full Backtest" button is clicked, the system processes the data and displays a comparison table with the following metrics for each of the 10 strategies:

| Metric | Description |
| :--- | :--- |
| **Strategy** | The name of the strategy (Strategy 1 to 10). |
| **Win Rate** | The percentage of trades that resulted in a profit. |
| **Trades** | The total number of signals generated and executed during the period. |
| **Max Consec. Losses** | The longest "losing streak," which is vital for understanding risk and drawdown. |

## 4. Technical Implementation

### Data Retrieval and Caching
To ensure speed and efficiency, the backtester uses a **1-hour caching mechanism**:
- When a backtest is requested, the bot checks `data/cache_[symbol]_[days]d.csv`.
- If the file exists and is less than 1 hour old, it is reused.
- Otherwise, the bot fetches fresh 5-minute candles from the Deriv API.

### Processing Logic
1.  **Indicator Calculation:** The bot adds RSI, MACD, ADX, and other technical indicators to the historical data.
2.  **Signal Generation:** The `ut_bot` function is applied with the specific sensitivity and ATR parameters for each strategy.
3.  **Backtest Engine:** The `Backtester` class simulates the trades using the **3-candle exit rule** (15-minute hold).
4.  **Result Aggregation:** The results are summarized and sent back to the UI via a JSON response.

## 5. Limitations

- **No ML Filtering in UI Backtest:** The current UI backtester evaluates the **raw** UT Bot signals without the Machine Learning filter. This provides a "baseline" performance. In contrast, the live bot and the static reports in the `Profitable strategy/` folder include the ML filter.
- **API Limits:** Large backtests (e.g., 365 days) may take a few moments to fetch data if not already cached.
