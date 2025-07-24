try:
    import websocket
except ImportError:
    print("Please install 'websocket-client' package")
    exit(1)

import json
import pandas as pd
import pandas_ta
import threading
import pytz
from datetime import datetime, time
from telegram import Bot
import finnhub

# CONFIG
FINNHUB_API_KEY = "d1vhbphr01qqgeelhtj0d1vhbphr01qqgeelhtjg"
TELEGRAM_TOKEN = "7769081812:AAG1nMhPiFMvsVdmkTWr6k-p78e-Lj9atRQ"
TELEGRAM_CHAT_ID = "1131774812"
SYMBOLS = ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT']
DURATIONS = ['1m', '5m', '10m', '15m']
IST = pytz.timezone('Asia/Kolkata')
price_data = {symbol: [] for symbol in SYMBOLS}

def is_trading_time():
    now = datetime.now(IST).time()
    return time(1, 0) <= now <= time(23, 0)

def validate_finnhub_api_key(api_key):
    try:
        client = finnhub.Client(api_key=api_key)
        client.quote('AAPL')
        print("✅ Finnhub API Key is valid")
        return True
    except Exception as e:
        print(f"❌ Invalid API Key: {e}")
        return False

def calculate_indicators(df):
    try:
        df['close'] = df['close'].astype(float)
        df['rsi'] = pandas_ta.rsi(df['close'], length=14)
        df['ema50'] = pandas_ta.ema(df['close'], length=50)
        df['ema200'] = pandas_ta.ema(df['close'], length=200)
        macd = pandas_ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        return df
    except Exception as e:
        print(f"Indicator calc error: {e}")
        return df

def generate_signal(symbol, df):
    if len(df) < 50:
        print(f"Not enough data for {symbol}")
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if latest['close'] > prev['close']:
        return {'direction': 'up', 'reason': 'Price increased', 'price': latest['close']}
    elif latest['close'] < prev['close']:
        return {'direction': 'down', 'reason': 'Price decreased', 'price': latest['close']}
    return None

def send_telegram_message(message, durations):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        for duration in durations:
            full_msg = f"{message}, Trade for: {duration}"
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_msg)
            print(f"📩 Sent to Telegram: {full_msg}")
    except Exception as e:
        print(f"Telegram error: {e}")

def on_message(ws, message):
    if not is_trading_time():
        print("⏳ Outside trading hours (1 AM–11 PM IST)")
        return
    try:
        data = json.loads(message)
        if 'data' in data:
            for tick in data['data']:
                symbol = tick.get('s')
                price = tick.get('p')
                timestamp = datetime.fromtimestamp(tick.get('t') / 1000, tz=IST)
                if symbol and price:
                    price_data[symbol].append({'time': timestamp, 'close': price})
                    price_data[symbol] = price_data[symbol][-300:]
                    df = pd.DataFrame(price_data[symbol])
                    df = calculate_indicators(df)
                    signal = generate_signal(symbol, df)
                    if signal:
                        msg = (f"📈 Make {signal['direction'].upper()} on {symbol} "
                               f"at {timestamp.strftime('%H:%M:%S %Z')}, "
                               f"Reason: {signal['reason']}, Price: {signal['price']}")
                        send_telegram_message(msg, DURATIONS)
    except Exception as e:
        print(f"Processing error: {e}")

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, code, msg):
    print(f"WebSocket closed: {code} - {msg}")

def on_open(ws):
    print("🔗 WebSocket connected")
    for symbol in SYMBOLS:
        ws.send(json.dumps({'type': 'subscribe', 'symbol': symbol}))
        print(f"📡 Subscribed to {symbol}")

def start_websocket():
    if not validate_finnhub_api_key(FINNHUB_API_KEY):
        return
    url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    thread = threading.Thread(target=start_websocket, daemon=True)
    thread.start()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("👋 Shutting down...")
