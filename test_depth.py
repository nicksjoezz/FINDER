import asyncio
from deriv_api import DerivAPI
from datetime import datetime, timedelta

async def test_depth():
    api = DerivAPI(app_id=1089)
    symbol = 'R_100'
    granularity = 300
    end_time = int(datetime.now().timestamp())
    total = 0
    current_end = end_time

    for i in range(50):
        try:
            # Reconnect or use new API object if needed, but let's try just catching error
            response = await api.ticks_history({
                'ticks_history': symbol,
                'end': str(current_end),
                'adjust_start_time': 1,
                'count': 5000,
                'granularity': granularity,
                'style': 'candles'
            })
            if 'error' in response:
                print(f"Fetch {i+1}: API Error: {response['error'].get('message', response['error'])}")
                break
            if 'candles' not in response or not response['candles']:
                print(f"Fetch {i+1}: No more candles.")
                break

            count = len(response['candles'])
            total += count
            print(f"Fetch {i+1}: Got {count} candles. Total: {total}. Earliest: {datetime.fromtimestamp(response['candles'][0]['epoch'])}")
            current_end = response['candles'][0]['epoch'] - 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Fetch {i+1}: Error: {e}")
            break

    await api.disconnect()

if __name__ == "__main__":
    asyncio.run(test_depth())
