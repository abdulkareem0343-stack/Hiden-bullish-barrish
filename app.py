import pandas as pd
import requests
import numpy as np

# KuCoin Public API Endpoint (No API Key Required)
KUCOIN_BASE_URL = "https://api.kucoin.com"

def get_usdt_pairs():
    """KuCoin se tamaam Active USDT Pairs fetch karta hai"""
    url = f"{KUCOIN_BASE_URL}/api/v1/symbols"
    res = requests.get(url).json()
    pairs = [item['symbol'] for item in res['data'] if item['symbol'].endswith('-USDT') and item['enableTrading']]
    return pairs

def get_klines(symbol, timeframe="1 hour"):
    """Candlestick data fetch karta hai"""
    # Timeframe mapping for KuCoin: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day
    tf_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    type_param = tf_map.get(timeframe, "1hour")
    
    url = f"{KUCOIN_BASE_URL}/api/v1/market/candles?symbol={symbol}&type={type_param}"
    try:
        res = requests.get(url, timeout=5).json()
        if res['code'] == '200000' and res['data']:
            df = pd.DataFrame(res['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df = df.iloc[::-1].reset_index(drop=True)  # Oldest to newest
            df['close'] = df['close'].astype(float)
            df['low'] = df['low'].astype(float)
            df['high'] = df['high'].astype(float)
            return df
    except Exception as e:
        return None
    return None

def calculate_rsi(df, period=14):
    """RSI Indicator Calculate karta hai"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def find_divergence(df):
    """Hidden Bullish aur Hidden Bearish Scanner"""
    if df is None or len(df) < 50:
        return None

    # Structural local peaks / troughs
    p_low1, p_low2 = df['low'].iloc[-15], df['low'].iloc[-1]
    rsi_low1, rsi_low2 = df['rsi'].iloc[-15], df['rsi'].iloc[-1]

    p_high1, p_high2 = df['high'].iloc[-15], df['high'].iloc[-1]
    rsi_high1, rsi_high2 = df['rsi'].iloc[-15], df['rsi'].iloc[-1]

    # 1. Hidden Bullish Divergence (Price HL + RSI LL)
    if (p_low2 > p_low1) and (rsi_low2 < rsi_low1):
        return "HIDDEN BULLISH 🟢"

    # 2. Hidden Bearish Divergence (Price LH + RSI HH)
    if (p_high2 < p_high1) and (rsi_high2 > rsi_high1):
        return "HIDDEN BEARISH 🔴"

    return None

def scan_market():
    print("🔍 Fetching KuCoin Pairs...")
    pairs = get_usdt_pairs()[:50]  # Top 50 pairs
    print(f"Scanning {len(pairs)} USDT Pairs...\n")

    results = []
    for symbol in pairs:
        df = get_klines(symbol, timeframe="1h")
        if df is not None:
            df = calculate_rsi(df)
            div_type = find_divergence(df)
            if div_type:
                results.append({"Symbol": symbol, "Signal": div_type, "Price": df['close'].iloc[-1], "RSI": round(df['rsi'].iloc[-1], 2)})

    res_df = pd.DataFrame(results)
    print("\n================ SCANNER RESULTS ================")
    if not res_df.empty:
        print(res_df.to_string(index=False))
    else:
        print("Filhal kisi coin par Hidden Divergence nahi mili.")

if __name__ == "__main__":
    scan_market()
