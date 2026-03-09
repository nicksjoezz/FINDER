# Strategy Lab & Performance Documentation

## Performance Metrics

### Neural Accuracy
The win rate achieved by the strategy after the Machine Learning Neural Filter has processed and filtered the raw UT Bot signals.

### Max Consecutive Losses
This metric tracks the longest streak of consecutive losing trades during the backtest period. It is a critical measure of risk and potential drawdown. Both "Raw" (indicator only) and "ML" (optimized) values are provided for comparison.

## Backtesting Parameters

- **Win Payout:** +95% of stake.
- **Loss Penalty:** -100% of stake.
- **Staking:** Dynamic Compounding. The stake for each trade is calculated as a percentage of the **available balance at the time of the trade**.
- **Minimum Stake:** The simulation enforces a minimum stake of $0.35 (Deriv standard).
