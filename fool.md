# How the Trading Bot Works (Simple Version)

Imagine you have two friends helping you trade: **The Scout** and **The Smart Coach**.

### 1. The Startup: Homework Time
When you first turn the bot on, it doesn't start trading immediately. Instead, it spends a few seconds "doing its homework."
- It looks at the last 4 months of market history.
- It studies every time **The Scout** gave a signal and checks if it would have made money or lost money.
- It builds a "cheat sheet" of which market conditions are good and which are bad.

### 2. The Scout (UT Bot)
This friend is always watching the charts. They look for specific patterns in price movement.
- When they see a pattern they like, they shout: **"Hey! I think we should Buy/Sell now!"**
- However, the Scout is a bit impulsive and sometimes makes mistakes.

### 3. The Smart Coach (Machine Learning Filter)
Before you actually spend any money, the **Smart Coach** stops the Scout and looks at their "cheat sheet."
- The Coach checks things like: "Is the market too crazy right now?" or "Is the trend too weak?"
- If the Coach thinks the Scout is likely to be wrong based on what happened in the past, they say: **"No, stay out. This one looks like a loser."**
- If the Coach agrees, the bot places the trade.

#### Is every Coach the same?
**No!** Even though all Coaches use the same tools (like RSI and MACD), each Coach is **custom-trained** for their specific Scout and Symbol.
- A Coach for **Volatility 100** knows how that specific market behaves.
- A Coach for **Strategy 1** learns the specific mistakes that Strategy 1 usually makes.
- When you start the bot, it builds a **unique Coach** just for the combination you picked. It's like having a specialized trainer for every single sport!

### 4. The 15-Minute Rule (3-Candle Exit)
Once the trade is placed, the bot doesn't get greedy or scared. It follows a very simple rule:
- It waits for exactly **3 candles** (since each candle is 5 minutes, that's **15 minutes** total).
- After 15 minutes, it closes the trade no matter what.
- It doesn't use complicated "Stop Losses" or "Take Profits" that can get hit by market noise; it just relies on the time.

### Summary
1. **Bot starts** -> Studies the past.
2. **The Scout** says "Go!"
3. **The Smart Coach** says "Yes" or "No".
4. **The Bot** trades and waits 15 minutes.
5. **Collect Profit.** (Repeat)
