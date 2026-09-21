import streamlit as st
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Advanced KuCoin Scanner", page_icon="⚡", layout="wide")

st.title("⚡ Advanced KuCoin Hidden Divergence Scanner")

KUCOIN_BASE_URL = "https://api.kucoin.com"

@st.cache_data(ttl=300)
def fetch_all_usdt_pairs():
    try:
        url = f"{KUCOIN_BASE_URL}/api/v1/symbols"
        res = requests.get(url, timeout=10).json()
        if res['code'] == '200000':
            return [item['symbol'] for item in res['data'] if item['symbol'].endswith('-USDT') and item['enableTrading']]
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
    return []

def get_klines_data(symbol, timeframe):
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

def process_coin(symbol, timeframe, rsi_min, rsi_max, signal_filter):
    df = get_klines_data(symbol, timeframe)
    if df is None or len(df) < 30:
        return None

    rsi_series = RSIIndicator(close=df['close'], window=14).rsi()
    df['rsi'] = rsi_series

    current_rsi = df['rsi'].iloc[-1]
    current_price = df['close'].iloc[-1]

    if not (rsi_min <= current_rsi <= rsi_max):
        return None

    p_low1, p_low2 = df['low'].iloc[-12], df['low'].iloc[-1]
    rsi_low1, rsi_low2 = df['rsi'].iloc[-12], df['rsi'].iloc[-1]

    p_high1, p_high2 = df['high'].iloc[-12], df['high'].iloc[-1]
    rsi_high1, rsi_high2 = df['rsi'].iloc[-12], df['rsi'].iloc[-1]

    signal = None
    if (p_low2 > p_low1) and (rsi_low2 < rsi_low1):
        signal = "Hidden Bullish 🟢"
    elif (p_high2 < p_high1) and (rsi_high2 > rsi_high1):
        signal = "Hidden Bearish 🔴"

    if signal:
        if signal_filter != "All" and signal_filter not in signal:
            return None

        return {
            "Symbol": symbol,
            "Signal": signal,
            "Price": f"${current_price}",
            "RSI": round(current_rsi, 2),
            "Price Structure": f"{round(p_low1, 4)} ➔ {round(p_low2, 4)}",
            "RSI Structure": f"{round(rsi_low1, 1)} ➔ {round(rsi_low2, 1)}"
        }

    return None

# Sidebar Controls
st.sidebar.header("⚙️ Scanner Settings")
timeframe = st.sidebar.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=0)
coin_limit = st.sidebar.slider("Number of Coins to Scan:", min_value=50, max_value=600, value=500, step=50)

st.sidebar.subheader("🎯 RSI Filters")
rsi_range = st.sidebar.slider("RSI Range Filter:", 0, 100, (30, 70))
signal_type = st.sidebar.radio("Signal Type Filter:", ["All", "Bullish", "Bearish"])

if st.button("⚡ Start Advanced Market Scan"):
    all_pairs = fetch_all_usdt_pairs()
    scan_list = all_pairs[:coin_limit]

    st.info(f"Scanning **{len(scan_list)}** USDT pairs on KuCoin ({timeframe})...")
    progress_bar = st.progress(0)
    
    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                process_coin, symbol, timeframe, rsi_range[0], rsi_range[1], signal_type
            ): symbol for symbol in scan_list
        }

        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
            completed += 1
            progress_bar.progress(completed / len(scan_list))

    progress_bar.empty()

    if results:
        st.success(f"🔍 **{len(results)}** Signals Found!")
        
        # Compact Data Table Format
        df_results = pd.DataFrame(results)
        st.dataframe(
            df_results, 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.warning("Selected RSI Range aur Filters ke mutabiq koi coin nahi mila.")
