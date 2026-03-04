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

async def update_symbol_data(symbol, data_dir='data'):
    """
    Incrementally updates the symbol's CSV file with latest data.
    Maintains approx 1 year of history (~105k candles).
    """
    filepath = os.path.join(data_dir, f"{symbol}_5m_2y.csv")
    granularity = 300
    end_time = int(datetime.now().timestamp())

    # 1. Read existing data
    df_old = pd.DataFrame()
    last_epoch = 0
    if os.path.exists(filepath):
        try:
            df_old = pd.read_csv(filepath)
            if not df_old.empty:
                last_epoch = int(df_old['epoch'].max())
        except Exception as e:
            sys.stderr.write(f"Error reading {filepath}: {e}\n")

    # 2. Fetch missing data
    # We fetch from last_epoch + granularity to avoid overlap
    start_time = last_epoch + granularity if last_epoch > 0 else int((datetime.now() - timedelta(days=366)).timestamp())

    if end_time - start_time < granularity:
        sys.stderr.write(f"Data for {symbol} is already up to date.\n")
        return df_old

    sys.stderr.write(f"Updating {symbol} from {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}\n")
    df_new = await get_historical_data(symbol, start_time, end_time, granularity)

    if df_new.empty:
        return df_old

    # 3. Merge and prune
    df_combined = pd.concat([df_old, df_new]).drop_duplicates(subset=['epoch']).sort_values('epoch')

    # Keep only the last 106,000 candles (~1 year)
    if len(df_combined) > 106000:
        df_combined = df_combined.tail(106000)

    # 4. Save
    os.makedirs(data_dir, exist_ok=True)
    df_combined.to_csv(filepath, index=False)
    sys.stderr.write(f"Saved {len(df_combined)} total candles for {symbol} (Added {len(df_new)})\n")
    return df_combined

async def main():
    symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']
    for symbol in symbols:
        await update_symbol_data(symbol)

if __name__ == "__main__":
    asyncio.run(main())
