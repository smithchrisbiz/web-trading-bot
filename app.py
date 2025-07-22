try:
    import websocket  # Should resolve to websocket-client
except ImportError:
    print("websocket-client package not found. Please run 'pip install websocket-client' in the shell and try again.")
    exit(1)

import json
import pandas as pd
import pandas_ta
import asyncio
import threading
import pytz
from datetime import datetime, time
import telegram
import finnhub

# Configuration (hardcoded for web environment)
FINNHUB_API_KEY = "d1vhbphr01qqgeelhtj0d1vhbphr01qqgeelhtjg"
TELEGRAM_TOKEN = "7769081812:AAG1nMhPiFMvsVdmkTWr6k-p78e-Lj9atRQ"
TELEGRAM_CHAT_ID = "1131774812"
SYMBOLS = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'BINANCE:BTCUSDT', 'BINANCE:ETHUSDT']
DURATIONS = ['5m']  # Simplified to one duration
IST = pytz.timezone('Asia/Kolkata')

# Store latest price data
price_data = {symbol: [] for symbol in SYMBOLS}

# Check if current time is within trading window (set to 0100-2300 IST)
def is_trading_time():
    now = datetime.now(IST).time()
    start_time = time(1, 0)  # 0100 IST
    end_time = time(23, 0)   # 2300 IST
    return start_time <= now <= end_time

# Validate Finnhub API Key
def validate_finnhub_api_key(api_key):
    try:
        finnhub_client = finnhub.Client(api_key=api_key)
        finnhub_client.quote('AAPL')  # Test with a known symbol
        print("Finnhub API Key is valid")
        return True
    except Exception as e:
        print(f"Finnhub API Key validation failed: {e}")
        return False

# Calculate indicators and generate signals
def calculate_indicators(df):
    try:
        df['close'] = df['close'].astype(float)
        df['rsi'] = pandas_ta.rsi(df['close'], length=14)
        df['ema50'] = pandas_ta.ema(df['close'], length=50)
        df['ema200'] = pandas_ta.ema(df['close'], length=200)
        df['macd'] = pandas_ta.macd(df['close'], fast=12, slow=26, signal=9)['MACD_12_26_9']
        df['macd_signal'] = pandas_ta.macd(df['close'], fast=12, slow=26, signal=9)['MACDs_12_26_9']
        return df
    except Exception as e:
        print(f"Indicator calculation error: {e}")
        return df

def generate_signal(symbol, df):
    if len(df) < 50:  # Minimum data points
        print(f"Insufficient data for {symbol}: {len(df)} rows")
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    # Basic signal based on price change
    if latest['close'] > prev['close']:
        reason = "Price increased"
        return {'direction': 'up', 'reason': reason, 'duration': DURATIONS[0], 'price': latest['close']}
    elif latest['close'] < prev['close']:
        reason = "Price decreased"
        return {'direction': 'down', 'reason': reason, 'duration': DURATIONS[0], 'price': latest['close']}
    return None

# Send signal to Telegram
async def send_telegram_message(message):
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print(f"Telegram message sent: {message}")
    except Exception as e:
        print(f"Telegram error: {e}")

# WebSocket handler
def on_message(ws, message):
    if not is_trading_time():
        print("Outside trading window (0100-2300 IST), skipping message")
        return
    try:
        data = json.loads(message)
        print(f"Received WebSocket data: {data}")
        if 'data' in data:
            for tick in data['data']:
                print(f"Processing tick: {tick}")
                symbol = tick.get('s')
                price = tick.get('p')
                timestamp = datetime.fromtimestamp(tick.get('t', 0) / 1000, tz=IST) if tick.get('t') else datetime.now(IST)
                if symbol and price is not None:
                    price_data[symbol].append({'time': timestamp, 'close': price})
                    print(f"Added to {symbol}: {price} at {timestamp}")
                    if len(price_data[symbol]) > 300:
                        price_data[symbol] = price_data[symbol][-300:]
                    df = pd.DataFrame(price_data[symbol])
                    df = calculate_indicators(df)
                    signal = generate_signal(symbol, df)
                    if signal:
                        message = (f"Make {signal['direction']} on {symbol} at {timestamp.strftime('%H:%M:%S %Z')}, "
                                  f"Reason: {signal['reason']}, Trade for: {signal['duration']}, "
                                  f"Current Price: {signal['price']}")
                        asyncio.run(send_telegram_message(message))
                else:
                    print(f"Invalid tick data: {tick}")
    except Exception as e:
        print(f"Error processing message: {e}")

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket closed: {close_status_code} - {close_msg}")

def on_open(ws):
    print("WebSocket connection opened")
    for symbol in SYMBOLS:
        ws.send(json.dumps({'type': 'subscribe', 'symbol': symbol}))
        print(f"Subscribed to {symbol}")

# Start WebSocket in a separate thread
def start_websocket():
    if not validate_finnhub_api_key(FINNHUB_API_KEY):
        print("Invalid Finnhub API Key. Aborting WebSocket connection.")
        return
    ws_url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    print(f"Attempting to connect to {ws_url}")
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        ws.run_forever()
    except AttributeError as e:
        print(f"WebSocketApp error: {e}. Please ensure 'pip install websocket-client==1.8.0' was successful.")
    except Exception as e:
        print(f"Unexpected error in start_websocket: {e}")

if __name__ == '__main__':
    # Start WebSocket in a background thread
    websocket_thread = threading.Thread(target=start_websocket, daemon=True)
    websocket_thread.start()
    # Keep the main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down...")
