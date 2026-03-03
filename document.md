# Analysis of Profitable Strategies

This document provides a comprehensive overview of the research findings and observations regarding the trading strategies stored in the `Profitable strategy/` directory.

## 1. Directory Structure and Overview

The `Profitable strategy/` directory contains backtesting results for three synthetic index symbols:
- **R_100 (Volatility 100 Index)**
- **R_50 (Volatility 50 Index)**
- **R_75 (Volatility 75 Index)**

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
The integration of the ML Filter results in exceptionally high win rates across the board:
- **R_75 Strategy 1:** 92.63% Win Rate (1,926 trades)
- **R_100 Strategy 10:** 91.85% Win Rate (1,386 trades)
- **R_50 Strategy 9:** 97.06% Win Rate (510 trades)

### Trade Frequency vs. Sensitivity
- **Lower Sensitivity (e.g., a=1):** Generates more signals (2,400+ trades) but may have slightly lower win rates.
- **Higher Sensitivity (e.g., a=3):** Generates fewer, higher-conviction signals (approx. 500 trades) with win rates exceeding 95%.

### Data and Training
- **Training Depth:** Limited by the Deriv API to approximately **30,000 to 35,000 candles** (roughly 104 to 121 days).
- **Consistency:** 60-day interval analysis shows stable performance, with maximum consecutive losses typically restricted to 2-4 trades.

## 5. Technical Implementation Details

The system is designed for robustness:
- **Automatic Training:** The ML model is re-trained specifically for each symbol upon bot startup.
- **Thresholds:** A minimum of **200 historical signals** is required to train the ML filter, ensuring statistical significance.
- **Environment:** Backtesting and logs indicate a reference system clock in the year **2026**.

## 6. Conclusion

The strategies documented in this folder represent highly optimized configurations for Deriv Rise/Fall options. The synergy between the UT Bot's trend-following signals and the Random Forest's ability to filter out high-risk market conditions provides a significant statistical edge in the 5m timeframe for synthetic indices.
