import streamlit as st
import os
import glob
import json
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import sys
#from utils.logger import logger


from pages.utils.stock_chart_generator import create_stock_charts
import pages.utils.stock_utils as stock_utils
st.set_page_config(page_title="IPO Stock Charts", page_icon="🚀", layout="wide")


current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)


CHART_FOLDER = os.path.join(project_root, "latest_ipo_stocks_charts")


if project_root not in sys.path:
    sys.path.insert(0, project_root)



# IPO_STOCKS = [
#     "CORDELIA.NS", "CSM.NS","AASTHA.NS",
#     "RAMBHAJO.NS", "TURTLEMINT.NS", "HEXAGON.NS", "CMRGREEN.NS", "BAGMANE.BO",
#     "KISSHT.NS", "CITIUSINVT.BO", "OMPOWER.NS", "AMIRCHAND.NS",
#     "POWERICA.NS", "SAIPARENT.NS", "CMPDI.NS", "GSPCROP.NS",
#     "RIIT.BO", "INNOVISION.NS", "RSL.NS", "SEDEMAC.NS",
#     "OMNI.NS", "PNGSREVA.NS", "SRTL.NS", "CLEANMAX.NS",
#     "GAUDIUMIVF.NS", "AYE.NS", "FRACTAL.NS", "SHADOWFAX.NS",
#     "AMAGI.NS", "BHARATCOAL.NS"
# ]

dataframe_ipo_stocks = pd.read_excel(r'C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Tickers\ipo_symbols_30_sep_2026_final.xlsx')

IPO_STOCKS = dataframe_ipo_stocks['Symbol Yahoo'].tolist()

RANKS_FILE = os.path.join(CHART_FOLDER, "ranks.json")

# ordering of stocks as per life time high (lower distance from high -> shown first)
try:
    with open(RANKS_FILE) as fh:
        stored_ranks = json.load(fh)
except Exception:
    stored_ranks = {}

# symbols missing from the ranks file keep the original excel order at the end
RANKED_STOCKS = sorted(IPO_STOCKS, key=lambda s: (stored_ranks.get(s, float("inf")), IPO_STOCKS.index(s)))





print(f'Chart folder path: {CHART_FOLDER}')

st.markdown("""
<style>
    .page-title { font-size: 1.8rem; font-weight: 800; color: #FF5722; margin-bottom: 0.5rem; }
    .section-title { font-size: 1.3rem; font-weight: 700; color: #FFFFFF; margin-top: 1rem; }
    .chart-card {
        background: linear-gradient(135deg, #0d2137 0%, #1a3a5f 100%);
        border: 1px solid #2a4a6f;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .chart-card:hover {
        border-color: #FF5722;
        box-shadow: 0 8px 25px rgba(255, 87, 34, 0.15);
    }
    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.8rem;
    }
    .stock-symbol {
        font-size: 1.3rem;
        font-weight: 800;
        color: #FFFFFF;
    }
    .stock-name {
        font-size: 0.85rem;
        color: #90CAF9;
    }
    .stock-price {
        font-size: 1.1rem;
        font-weight: 700;
    }
    .screener-btn {
        display: inline-block;
        background: linear-gradient(135deg, #FF5722 0%, #E64A19 100%);
        color: white;
        padding: 0.3rem 1rem;
        border-radius: 6px;
        text-decoration: none;
        font-size: 0.8rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .screener-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(255, 87, 34, 0.3);
    }
    .stock-meta {
        font-size: 0.8rem;
        color: #546E7A;
        margin-top: 0.3rem;
    }
    .stat-chip {
        display: inline-block;
        background: #1a3a5f;
        border: 1px solid #2a4a6f;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.75rem;
        color: #B0BEC5;
        margin: 0.2rem;
    }
    .progress-text {
        font-size: 0.85rem;
        color: #90CAF9;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">🚀 Latest IPO Stock Charts</div>', unsafe_allow_html=True)
st.caption("Candlestick charts for recently listed IPO stocks with direct links to Screener.in for detailed fundamental analysis.")

col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])

with col_ctrl1:
    st.markdown(f"**📂 Charts Location:** `{CHART_FOLDER}`")
    st.markdown(f"**📊 Total Stocks Tracked:** {len(IPO_STOCKS)}")

with col_ctrl2:
    chart_period = st.selectbox(
        "**Chart Period**",
        ["3mo", "6mo", "1y", "2y"],
        index=2,
        help="Select the time period for chart data"
    )

current_charts = set()
if os.path.exists(CHART_FOLDER):
    current_charts = {os.path.basename(f) for f in glob.glob(os.path.join(CHART_FOLDER, "*.png"))}

with col_ctrl3:
    st.markdown("<br>", unsafe_allow_html=True)
    regenerate = st.button("🔄 Regenerate All Charts", type="primary", use_container_width=True)



if regenerate:
    print("IPO chart regeneration requested")
    st.warning(f"⏳ Regenerating {len(IPO_STOCKS)} charts with period '{chart_period}'. This may take a minute...")

    progress_bar = st.progress(0, text="Starting chart generation...")

    try:
        os.makedirs(CHART_FOLDER, exist_ok=True)
        for f in glob.glob(os.path.join(CHART_FOLDER, "*.png")):
            try:
                os.remove(f)
            except Exception:
                pass

        total = len(IPO_STOCKS)


        # ranking of stocks as per life time high 
        ranks = {}

        for idx, symbol in enumerate(IPO_STOCKS):
            progress_text = f"[{idx+1}/{total}] Downloading {symbol}..."
            progress_bar.progress((idx) / total, text=progress_text)
            print(f"Regenerating chart: {symbol}")

            try:
                ticker_obj = yf.Ticker(symbol)
                df = ticker_obj.history(period=chart_period)
                
                if not df.empty:
                    file_path = os.path.join(CHART_FOLDER, f"{symbol}.png")
                    import mplfinance as mpf
                    mpf.plot(
                        df,
                        type='candle',
                        volume=False,
                        title=f'{symbol}',
                        figsize=(16, 7),
                        savefig=file_path
                    )
                    print(f"Chart saved: {symbol}")

                    high_close = df["Close"].max()
                    latest_close = df["Close"].iloc[-1]
                    

                    # here we are getting the stocks how much away from life time high 
                    ranks[symbol] = float(round((high_close-latest_close)/high_close,2))


            except Exception as e:
                print(f"Failed to generate chart for {symbol}: {e}")

        # persist ranks so the gallery can be ordered on later runs too
        try:
            with open(RANKS_FILE, "w") as fh:
                json.dump(ranks, fh)
        except Exception as e:
            print(f"Failed to save ranks: {e}")

        print(f"ranks : {ranks}")


        progress_bar.progress(1.0, text="All charts regenerated!")
        time.sleep(0.5)
        progress_bar.empty()

        st.success(f"✅ Successfully regenerated {len(IPO_STOCKS)} IPO stock charts!")
        print("IPO chart regeneration completed")
        st.rerun()

    except Exception as e:
        st.error(f"Error during chart regeneration: {str(e)}")
        print("Chart regeneration failed")
        progress_bar.empty()

st.markdown("---")
st.markdown(f'<div class="section-title">📊 IPO Stock Charts Gallery</div>', unsafe_allow_html=True)

st.markdown(f"""
<div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
    <span class="stat-chip">📈 {len(IPO_STOCKS)} Stocks</span>
    <span class="stat-chip">🕐 Period: {chart_period}</span>
    <span class="stat-chip">🖼 Charts: {len(current_charts)}/{len(IPO_STOCKS)} available</span>
</div>
""", unsafe_allow_html=True)

st.caption("Click the 🔗 Screener button to view detailed fundamentals for any stock.")

stock_info_cache = {}

rows_needed = (len(RANKED_STOCKS) + 1) // 2

for row_idx in range(rows_needed):
    cols = st.columns(2)
    for col_idx in range(2):
        stock_idx = row_idx * 2 + col_idx
        if stock_idx >= len(RANKED_STOCKS):
            break

        symbol = RANKED_STOCKS[stock_idx]
        chart_path = os.path.join(CHART_FOLDER, f"{symbol}.png")
        chart_exists = os.path.exists(chart_path)

        screener_url = stock_utils.screener_company_url(symbol)
        yahoo_url = f"https://finance.yahoo.com/quote/{symbol}/"

        with cols[col_idx]:
            with st.container():
                st.markdown(f'<div class="chart-card">', unsafe_allow_html=True)

                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.markdown(f'<div class="stock-symbol">{symbol}</div>', unsafe_allow_html=True)

                with header_col2:
                    st.markdown(
                        f'<a href="{screener_url}" target="_blank" class="screener-btn">🔗 Screener</a>',
                        unsafe_allow_html=True
                    )

                if symbol not in stock_info_cache:
                    try:
                        ticker = yf.Ticker(symbol)
                        info = ticker.info
                        name = info.get("longName", symbol)
                        price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))
                        prev_close = info.get("previousClose", info.get("regularMarketPreviousClose", price))
                        change = (price - prev_close) if isinstance(price, (int, float)) and isinstance(prev_close, (int, float)) else 0
                        change_pct = (change / prev_close * 100) if isinstance(change, (int, float)) and isinstance(prev_close, (int, float)) and prev_close != 0 else 0
                        sector = info.get("sector", "N/A")
                        industry = info.get("industry", "")
                        market_cap = info.get("marketCap", 0)
                        pe = info.get("trailingPE", None)
                    except Exception:
                        name = symbol
                        price = "N/A"
                        change = 0
                        change_pct = 0
                        sector = "N/A"
                        industry = ""
                        market_cap = 0
                        pe = None

                    stock_info_cache[symbol] = {
                        "name": name,
                        "price": price,
                        "change": change,
                        "change_pct": change_pct,
                        "sector": sector,
                        "industry": industry,
                        "market_cap": market_cap,
                        "pe": pe,
                    }
                else:
                    name = stock_info_cache[symbol]["name"]
                    price = stock_info_cache[symbol]["price"]
                    change = stock_info_cache[symbol]["change"]
                    change_pct = stock_info_cache[symbol]["change_pct"]
                    sector = stock_info_cache[symbol]["sector"]
                    industry = stock_info_cache[symbol]["industry"]
                    pe = stock_info_cache[symbol]["pe"]

                change_color = "#4CAF50" if change >= 0 else "#f44336"
                change_icon = "📈" if change >= 0 else "📉"
                price_str = f"₹{price:.2f}" if isinstance(price, (int, float)) else str(price)
                change_str = f"{change_icon} {change:+.2f} ({change_pct:+.2f}%)" if isinstance(change, (int, float)) else "N/A"
                pe_str = f"P/E: {pe:.2f}" if pe else ""
                mc_str = f"₹{market_cap/1e7:.1f}Cr" if isinstance(market_cap, (int, float)) and market_cap >= 1e7 else (f"₹{market_cap/1e5:.1f}L" if isinstance(market_cap, (int, float)) else "")

                st.markdown(
                    f'<div class="stock-name">{name}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="stock-price" style="color:{change_color}">{price_str} <span style="font-size:0.85rem;color:{change_color}">{change_str}</span></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="stock-meta">{sector} {(" | " + industry) if industry else ""} {(" | " + pe_str) if pe_str else ""} {(" | " + mc_str) if mc_str else ""}</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<a href="{yahoo_url}" target="_blank" style="color:#1E88E5;font-size:0.75rem;">📈 Yahoo Finance →</a>',
                    unsafe_allow_html=True
                )

                if chart_exists:
                    st.image(chart_path, use_container_width=True)
                else:
                    st.warning(f"⚠ Chart not generated yet. Click **Regenerate All Charts** above.")

                st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

st.markdown(f'<div class="section-title">📋 All IPO Stocks Quick Reference</div>', unsafe_allow_html=True)

table_data = []
for symbol in IPO_STOCKS:
    screener_url = stock_utils.screener_company_url(symbol)

    if symbol in stock_info_cache:
        info = stock_info_cache[symbol]
        table_data.append({
            "Symbol": symbol,
            "Company": info["name"],
            "Price": f"₹{info['price']:.2f}" if isinstance(info['price'], (int, float)) else "N/A",
            "Change": f"{info['change_pct']:+.2f}" if isinstance(info['change_pct'], (int, float)) else "N/A",
            "Sector": info["sector"],
            "Chart": "✅" if os.path.exists(os.path.join(CHART_FOLDER, f"{symbol}.png")) else "❌",
            "Screener": f"[🔗 Open]({screener_url})",
        })
    else:
        table_data.append({
            "Symbol": symbol,
            "Company": symbol,
            "Price": "N/A",
            "Change": "N/A",
            "Sector": "N/A",
            "Chart": "✅" if os.path.exists(os.path.join(CHART_FOLDER, f"{symbol}.png")) else "❌",
            "Screener": f"[🔗 Open]({screener_url})",
        })

st.dataframe(
    pd.DataFrame(table_data),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Screener": st.column_config.LinkColumn("Screener", width="small"),
    }
)

st.markdown("---")
st.caption(f"🕒 Page loaded at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: Yahoo Finance | Charts: mplfinance")
st.caption("💡 Click the **Screener** button on any stock card to view detailed fundamental analysis including P&L, balance sheet, and ratios.")
