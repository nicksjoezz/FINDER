import pandas as pd
import numpy as np
import os
from strategy_utils import ut_bot, Backtester, analyze_performance
from indicators import add_indicators
from ml_filter import MLFilter

def run_optimized_strategies():
    symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']

    configs = [
        (1, 10, "UT Bot (1, 10) + ML Filter"),
        (2, 20, "UT Bot (2, 20) + ML Filter"),
        (3, 30, "UT Bot (3, 30) + ML Filter"),
        (1, 20, "UT Bot (1, 20) + ML Filter"),
        (2, 10, "UT Bot (2, 10) + ML Filter"),
        (3, 20, "UT Bot (3, 20) + ML Filter"),
        (1, 30, "UT Bot (1, 30) + ML Filter"),
        (2, 30, "UT Bot (2, 30) + ML Filter"),
        (3, 10, "UT Bot (3, 10) + ML Filter"),
        (1.5, 15, "UT Bot (1.5, 15) + ML Filter")
    ]

    output_dir = 'Profitable strategy'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, (a, c, desc) in enumerate(configs):
        strat_name = f"Strategy_{i+1}"
        # Skip if already exists
        if os.path.exists(f'{output_dir}/{strat_name}.txt'):
            continue

        all_trades = []
        for symbol in symbols:
            filepath = f'data/{symbol}_5m_2y.csv'
            if not os.path.exists(filepath): continue

            df = pd.read_csv(filepath)
            df = add_indicators(df)
            df_raw = ut_bot(df, a=a, c=c)
            raw_trades = Backtester(df_raw).run()

            if len(raw_trades) < 200: continue

            ml = MLFilter()
            if ml.train(df, raw_trades):
                df_filtered = ml.filter_signals(df_raw)
                final_trades = Backtester(df_filtered).run()
                if not final_trades.empty:
                    final_trades['symbol'] = symbol
                    all_trades.append(final_trades)

        if not all_trades:
            print(f"{strat_name} Failed")
            continue

        full_trades = pd.concat(all_trades)
        wr = full_trades['win'].mean()
        perf = analyze_performance(full_trades)

        with open(f'{output_dir}/{strat_name}.txt', 'w') as f:
            f.write(f"Strategy: {strat_name}\nDescription: {desc}\nOverall Win Rate: {wr:.2%}\nTrades: {len(full_trades)}\n\n{perf.to_string()}")
        print(f"{strat_name} Done. WR: {wr:.2%}")

if __name__ == "__main__":
    run_optimized_strategies()
