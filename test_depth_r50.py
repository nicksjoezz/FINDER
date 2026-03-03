import asyncio
from deriv_api import DerivAPI
from datetime import datetime

async def test_depth():
    api = DerivAPI(app_id=1089)
    symbol = 'R_50'
    granularity = 300
    end_time = int(datetime.now().timestamp())
    total = 0
    current_end = end_time

    for i in range(50):
        try:
            response = await api.ticks_history({
                'ticks_history': symbol,
                'end': str(current_end),
                'adjust_start_time': 1,
                'count': 5000,
                'granularity': granularity,
                'style': 'candles'
            })
            if 'error' in response: break
            if 'candles' not in response or not response['candles']: break

            candles = response['candles']
            new_end = candles[0]['epoch'] - 1
            if new_end >= current_end:
                print("Limit reached (jumped back or stayed same).")
                break

            count = len(candles)
            total += count
            print(f"Fetch {i+1}: Got {count} candles. Total: {total}. Earliest: {datetime.fromtimestamp(candles[0]['epoch'])}")
            current_end = new_end
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}")
            break

    await api.disconnect()

if __name__ == "__main__":
    asyncio.run(test_depth())
