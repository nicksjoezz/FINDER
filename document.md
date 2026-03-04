# Analysis of Profitable Strategies

This document provides a comprehensive overview of the research findings and observations regarding the trading strategies stored in the `Profitable strategy/` directory.

## 1. Directory Structure and Overview

The `Profitable strategy/` directory contains backtesting results for five synthetic index symbols:
- **R_100 (Volatility 100 Index)**
- **R_75 (Volatility 75 Index)**
- **R_50 (Volatility 50 Index)**
- **R_25 (Volatility 25 Index)**
- **R_10 (Volatility 10 Index)**

Each sub-directory contains up to 10 strategy files (`Strategy_1.txt` to `Strategy_10.txt`), documenting optimized parameters and their performance metrics.

## 2. Core Strategy Logic

The strategies employ a **hybrid approach** combining a classic momentum indicator with modern Machine Learning filtering.

### Base Indicator: UT Bot Alerts
The foundational signals are generated using the **UT Bot Alerts** algorithm, which consists of:
- **ATR Trailing Stop:** Uses Average True Range (ATR) to define dynamic support and resistance levels.
- **Sensitivity (a):** A multiplier for the ATR to adjust the "tightness" of the stop.
- **ATR Period (c):** The lookback period for volatility calculation.

### Machine Learning Filter
A **Random Forest Classifier** is applied to every raw signal. It evaluates the market context at the moment of the signal and only allows the trade if it predicts a "Win".

**ML Features used:**
1. **RSI (14):** Relative Strength Index (Momentum/Overbought/Oversold).
2. **MACD Histogram:** Trend momentum and divergence.
3. **ADX:** Average Directional Index (Trend strength vs. Ranging market).
4. **Bollinger Band %B:** Price position relative to volatility bands.
5. **EMA 200 Distance:** Normalized distance from the long-term trend line.

## 3. Execution Parameters

Based on the source code (`strategy_utils.py`), the backtesting and live trading follow these strict rules:
- **Timeframe:** 5-minute (5m) candles.
- **Entry:** Occurs at the **Open** of the candle immediately following the signal.
- **Exit:** Fixed holding period of **3 candles**.
- **Profit/Loss:** Determined by the difference between the Entry Open price and the Exit Close price.

## 4. Observations and Performance Metrics

### Win Rate Highlights
The integration of the ML Filter results in stable and profitable win rates over a full 1-year period:
- **R_10 Strategy 9:** 94.10% Win Rate (1,322 trades)
- **R_50 Strategy 9:** 92.21% Win Rate (1,489 trades)
- **R_100 Strategy 10:** 80.13% Win Rate (4,272 trades)

### Trade Frequency vs. Sensitivity
- **Lower Sensitivity (e.g., a=1):** Generates more signals (2,400+ trades) but may have slightly lower win rates.
- **Higher Sensitivity (e.g., a=3):** Generates fewer, higher-conviction signals (approx. 500 trades) with win rates exceeding 95%.

### Data and Training
- **Training Depth:** Optimized to use the maximum historical depth provided by the Deriv API, which is approximately **105,000 candles** (roughly **1 year** of data).
- **Consistency:** 60-day interval analysis shows stable performance across different market cycles, with maximum consecutive losses typically restricted to 2-4 trades.

## 5. Technical Implementation Details

The system is designed for robustness:
- **Centralized Model Management:** A dedicated `ModelManager` maintains 50 pre-trained models in memory, ensuring consistency between backtesting and live trading.
- **Continuous Learning:** The system automatically fetches fresh data and retrains all models every 24 hours at 00:05 UTC.
- **Thresholds:** A minimum of **200 historical signals** is required to train the ML filter, ensuring statistical significance.
- **Environment:** Backtesting and logs indicate a reference system clock in the year **2026**.

## 6. Conclusion

The strategies documented in this folder represent highly optimized configurations for Deriv Rise/Fall options. The synergy between the UT Bot's trend-following signals and the Random Forest's ability to filter out high-risk market conditions provides a significant statistical edge in the 5m timeframe for synthetic indices.
