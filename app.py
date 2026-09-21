import streamlit as st
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Advanced KuCoin Scanner", page_icon="⚡", layout="wide")

# Custom CSS for compact card design
st.markdown("""
<style>
    .coin-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .coin-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .coin-symbol {
        font-size: 15px;
        font-weight: bold;
        color: #1e1e1e;
    }
    .signal-bullish {
        background-color: #e6f4ea;
        color: #137333;
        font-size: 12px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
    }
    .signal-bearish {
        background-color: #fce8e6;
        color: #c5221f;
        font-size: 12px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
    }
    .coin-details {
        font-size: 13px;
        color: #4a4a4a;
        margin-bottom: 4px;
    }
    .coin-struct {
        font-size: 11px;
        color: #707070;
        border-top: 1px dashed #dedede;
        padding-top: 4px;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ KuCoin Hidden Divergence Scanner")

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
            "symbol": symbol,
            "signal": signal,
            "price": current_price,
            "rsi": round(current_rsi, 2),
            "p_low1": round(p_low1, 4),
            "p_low2": round(p_low2, 4),
            "rsi_low1": round(rsi_low1, 1),
            "rsi_low2": round(rsi_low2, 1)
        }

    return None

# Sidebar Controls
st.sidebar.header("⚙️ Scanner Settings")
timeframe = st.sidebar.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=0)
coin_limit = st.sidebar.slider("Number of Coins to Scan:", min_value=50, max_value=600, value=500, step=50)

st.sidebar.subheader("🎯 RSI Filters")
rsi_range = st.sidebar.slider("RSI Range Filter:", 0, 100, (30, 70))
signal_type = st.sidebar.radio("Signal Type Filter:", ["All", "Bullish", "Bearish"])

if st.button("⚡ Start Market Scan"):
    all_pairs = fetch_all_usdt_pairs()
    scan_list = all_pairs[:coin_limit]

    st.info(f"Scanning **{len(scan_list)}** USDT pairs ({timeframe})...")
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
        
        # Render Compact HTML Cards
        for item in results:
            signal_class = "signal-bullish" if "Bullish" in item['signal'] else "signal-bearish"
            card_html = f"""
            <div class="coin-card">
                <div class="coin-header">
                    <span class="coin-symbol">📌 {item['symbol']}</span>
                    <span class="{signal_class}">{item['signal']}</span>
                </div>
                <div class="coin-details">
                    <b>Price:</b> ${item['price']} &nbsp;|&nbsp; <b>RSI:</b> {item['rsi']}
                </div>
                <div class="coin-struct">
                    <b>Price Structure:</b> {item['p_low1']} ➔ {item['p_low2']} &nbsp;|&nbsp; 
                    <b>RSI Structure:</b> {item['rsi_low1']} ➔ {item['rsi_low2']}
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.warning("Selected RSI Range aur Filters ke mutabiq koi coin nahi mila.")
