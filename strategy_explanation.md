# Strategy Lab & Efficiency Documentation

## What is EFFICIENCY Δ?

**EFFICIENCY Δ** (Efficiency Delta) represents the quantitative improvement in win rate achieved by applying the symbol-specific Machine Learning neural filter over the raw UT Bot indicator signals.

### How it is calculated:
`Efficiency Δ = (ML Optimized Win Rate) - (Raw Indicator Win Rate)`

For example:
- If Strategy A has a **Raw Win Rate** of **55.0%**.
- After applying the **ML Neural Filter**, the **Optimized Win Rate** becomes **85.0%**.
- The **Efficiency Δ** is **+30.0%**.

### What it means:
A positive Efficiency Δ indicates that the Machine Learning model has successfully identified and blocked high-probability losing trades, thereby increasing the overall accuracy of the strategy. A higher delta suggests a more "efficient" use of capital, as fewer trades are taken but with a significantly higher success probability.

## Backtesting Parameters

- **Win Payout:** +95% of stake.
- **Loss Penalty:** -100% of stake.
- **Staking:** Fixed staking based on the user-defined "Risk per Trade (%)" of the initial "Seed Capital".
