import asyncio
import pandas as pd
from deriv_api import DerivAPI
import os
from datetime import datetime, timedelta
import sys

async def get_historical_data(symbol, start_time, end_time, granularity):
    api = DerivAPI(app_id=1089)

    all_candles = []
    current_end = end_time

    # Target approx 1 year of 5m data = 365 * 24 * 60 / 5 = 105,120 candles
    # Note: Deriv API currently limits historical 5m candles to ~105,000 for synthetic indices.
    target_count = 105500

    while len(all_candles) < target_count and current_end > start_time:
        sys.stderr.write(f"Fetching data for {symbol} up to {datetime.fromtimestamp(current_end)}\n")
        try:
            response = await api.ticks_history({
                'ticks_history': symbol,
                'end': str(current_end),
                'adjust_start_time': 1,
                'count': 5000,
                'granularity': granularity,
                'style': 'candles'
            })

            if 'error' in response:
                sys.stderr.write(f"API Error for {symbol}: {response['error']}\n")
                break

            if 'candles' not in response:
                sys.stderr.write(f"No candles in response for {symbol}: {response}\n")
                break

            candles = response['candles']
            if not candles:
                sys.stderr.write(f"Empty candles list for {symbol}\n")
                break

            all_candles.extend(candles[::-1])

            # The earliest candle in this batch
            new_end = candles[0]['epoch'] - 1
            if new_end >= current_end:
                # We've reached the earliest possible candle provided by the API
                break
            current_end = new_end

            sys.stderr.write(f"  Got {len(candles)} candles. Total: {len(all_candles)}\n")

            await asyncio.sleep(0.3) # Faster fetching

        except Exception as e:
            sys.stderr.write(f"An error occurred for {symbol}: {e}\n")
            break

    await api.disconnect()

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles)
    df = df.drop_duplicates(subset=['epoch']).sort_values('epoch')
    return df

async def main():
    symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']
    granularity = 300 # 5 minutes

    end_time = int(datetime.now().timestamp())
    start_time = int((datetime.now() - timedelta(days=366)).timestamp())

    os.makedirs('data', exist_ok=True)

    for symbol in symbols:
        df = await get_historical_data(symbol, start_time, end_time, granularity)
        if not df.empty:
            df.to_csv(f'data/{symbol}_5m_2y.csv', index=False)
            sys.stderr.write(f"Saved {len(df)} candles for {symbol}\n")
        else:
            sys.stderr.write(f"Failed to fetch data for {symbol}\n")

if __name__ == "__main__":
    asyncio.run(main())
