import streamlit as st
import pandas as pd
import requests

# Page Configuration
st.set_page_config(page_title="KuCoin Divergence Scanner", page_icon="📈", layout="wide")

st.title("📈 KuCoin Hidden Divergence Scanner")
st.write("Yeh app KuCoin par **Hidden Bullish** aur **Hidden Bearish** divergence detect karti hai.")

KUCOIN_BASE_URL = "https://api.kucoin.com"

@st.cache_data(ttl=300)
def get_usdt_pairs():
    try:
        url = f"{KUCOIN_BASE_URL}/api/v1/symbols"
        res = requests.get(url, timeout=10).json()
        if res['code'] == '200000':
            return [item['symbol'] for item in res['data'] if item['symbol'].endswith('-USDT') and item['enableTrading']]
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
    return []

def get_klines(symbol, timeframe="1h"):
    tf_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    type_param = tf_map.get(timeframe, "1hour")
    url = f"{KUCOIN_BASE_URL}/api/v1/market/candles?symbol={symbol}&type={type_param}"
    
    try:
        res = requests.get(url, timeout=5).json()
        if res['code'] == '200000' and res['data']:
            df = pd.DataFrame(res['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df = df.iloc[::-1].reset_index(drop=True)
            df['close'] = df['close'].astype(float)
            df['low'] = df['low'].astype(float)
            df['high'] = df['high'].astype(float)
            return df
    except Exception:
        return None
    return None

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def find_divergence(df):
    if df is None or len(df) < 30:
        return None

    # Compare recent lows/highs for hidden divergence
    p_low1, p_low2 = df['low'].iloc[-10], df['low'].iloc[-1]
    rsi_low1, rsi_low2 = df['rsi'].iloc[-10], df['rsi'].iloc[-1]

    p_high1, p_high2 = df['high'].iloc[-10], df['high'].iloc[-1]
    rsi_high1, rsi_high2 = df['rsi'].iloc[-10], df['rsi'].iloc[-1]

    # Hidden Bullish: Higher Low in Price, Lower Low in RSI
    if (p_low2 > p_low1) and (rsi_low2 < rsi_low1):
        return "Hidden Bullish 🟢"

    # Hidden Bearish: Lower High in Price, Higher High in RSI
    if (p_high2 < p_high1) and (rsi_high2 > rsi_high1):
        return "Hidden Bearish 🔴"

    return None

# User Controls
timeframe = st.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=1)
limit = st.slider("Kitne pairs scan karne hain?", min_value=10, max_value=100, value=30, step=10)

if st.button("🚀 Scan Market Now"):
    with st.spinner("KuCoin Pairs Scan ho rahe hain... Bas 10-15 seconds rukien."):
        pairs = get_usdt_pairs()[:limit]
        results = []

        for symbol in pairs:
            df = get_klines(symbol, timeframe)
            if df is not None and not df.empty:
                df = calculate_rsi(df)
                signal = find_divergence(df)
                if signal:
                    results.append({
                        "Symbol": symbol,
                        "Signal": signal,
                        "Price (USDT)": df['close'].iloc[-1],
                        "RSI": round(df['rsi'].iloc[-1], 2)
                    })

        if results:
            res_df = pd.DataFrame(results)
            st.success(f"Scan complete! {len(results)} signals mile hain:")
            st.dataframe(res_df, use_container_width=True)
        else:
            st.warning("Is waqt kisi coin par Hidden Divergence signal nahi mila.")
