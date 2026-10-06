import requests
import pandas as pd
import time
import yfinance as yf
import plotly.graph_objects as go
import streamlit as st

SECTOR_INDICES = [
    "NIFTY AUTO", "NIFTY BANK", "NIFTY CAPITAL MARKETS", "NIFTY CEMENT",
    "NIFTY CHEMICALS", "NIFTY COMMODITIES", "NIFTY CONGLOMERATE",
    "NIFTY CONSUMER DURABLES", "NIFTY CORE HOUSING", "NIFTY ENERGY",
    "NIFTY FINANCIAL SERVICES", "NIFTY FINANCIAL SERVICES 25/50",
    "NIFTY FINANCIAL SERVICES EX-BANK", "NIFTY FMCG",
    "NIFTY HEALTHCARE INDEX", "NIFTY HOUSING", "NIFTY INDIA CONSUMPTION",
    "NIFTY INDIA DEFENCE", "NIFTY INDIA DIGITAL",
    "NIFTY INDIA INFRASTRUCTURE & LOGISTICS", "NIFTY INDIA INTERNET",
    "NIFTY INDIA MANUFACTURING", "NIFTY INDIA TOURISM",
    "NIFTY INFRASTRUCTURE", "NIFTY IT", "NIFTY MEDIA", "NIFTY METAL",
    "NIFTY MNC", "NIFTY MOBILITY", "NIFTY OIL & GAS", "NIFTY PHARMA",
    "NIFTY PRIVATE BANK", "NIFTY PSU BANK", "NIFTY REALTY",
    "NIFTY RURAL", "NIFTY SERVICES SECTOR",
    "NIFTY TRANSPORTATION & LOGISTICS",
    "NIFTY EV & NEW AGE AUTOMOTIVE",
    "NIFTY NON-CYCLICAL CONSUMER",
    "NIFTY REITS & REALTY",
]

INDEX_MAP = {
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY CAPITAL MARKETS": "NIFTY_CAPITAL_MKT.NS",
    "NIFTY CEMENT": 'NIFTY_CEMENT.NS',
    "NIFTY CHEMICALS": "NIFTY_CHEMICALS.NS",
    "NIFTY COMMODITIES": "^CNXCOMMODT",
    "NIFTY CONGLOMERATE": None,
    "NIFTY CONSUMER DURABLES": "^CNXCONSUMER",
    "NIFTY CORE HOUSING": "NIFTY_COREHOUSING.NS",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY FINANCIAL SERVICES": "^CNXFINANCE",
    "NIFTY FINANCIAL SERVICES 25/50": "^CNXFIN",
    "NIFTY FINANCIAL SERVICES EX-BANK": None,
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY HEALTHCARE INDEX": "^CNXPHARMA",  # closest available
    "NIFTY HOUSING": "NIFTY_HOUSING.NS",
    "NIFTY INDIA CONSUMPTION": "^CNXCONSUMPTION",
    "NIFTY INDIA DEFENCE": None,
    "NIFTY INDIA DIGITAL": None,
    "NIFTY INDIA INFRASTRUCTURE & LOGISTICS": None,
    "NIFTY INDIA INTERNET": None,
    "NIFTY INDIA MANUFACTURING": None,
    "NIFTY INDIA TOURISM": None,
    "NIFTY INFRASTRUCTURE": "^CNXINFRA",
    "NIFTY IT": "^CNXIT",
    "NIFTY MEDIA": "^CNXMEDIA",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY MNC": "^CNXMNC",
    "NIFTY MOBILITY": None,
    "NIFTY OIL & GAS": "^CNXOILGAS",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY PRIVATE BANK": "^NIFTYPVTBANK",
    "NIFTY PSU BANK": "^CNXPSUBANK",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY RURAL": "^CNXRURAL",
    "NIFTY SERVICES SECTOR": "^CNXSERVICE",
    "NIFTY TRANSPORTATION & LOGISTICS": None,
    "NIFTY EV & NEW AGE AUTOMOTIVE": None,
    "NIFTY NON-CYCLICAL CONSUMER": None,
    "NIFTY REITS & REALTY": None,
}


def fetch_all_indices():
    base_url = "https://www.nseindia.com"
    api_url = "https://www.nseindia.com/api/allIndices"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/market-data/live-equity-market",
    }

    session = requests.Session()
    session.get(base_url, headers=headers)
    time.sleep(2)

    response = session.get(api_url, headers=headers)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data["data"])
    return df


def fetch_index_history(yf_symbol, period="3mo"):
    ticker = yf.Ticker(yf_symbol)
    hist = ticker.history(period=period)
    return hist


def main():
    st.set_page_config(page_title="Sector Indices", page_icon="📊", layout="wide")

    st.title("Sector Indices")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col3:
        period = st.selectbox("Chart Period", ["1mo", "3mo", "6mo", "1y"], index=3)


    if st.button("Fetch Sector Indices", type="primary"):
        with st.spinner("Fetching sector indices data from NSE..."):
            try:
                df = fetch_all_indices()
                sector_df = df[df["index"].isin(SECTOR_INDICES)].copy()
                sector_df = sector_df.sort_values(by="percentChange", ascending=False).reset_index(drop=True)

                st.subheader("All Sector Indices")
                cols = ["index", "last", "percentChange", "variation", "open", "high", "low", "previousClose"]
                avail = [c for c in cols if c in sector_df.columns]
                st.dataframe(sector_df[avail], use_container_width=True, hide_index=True)

                n=st.selectbox('Top Charts', [i for i in range(1,50)], index=5)
                top5 = sector_df.head(n)
                st.subheader(f"Top {n} Sector Indices - Price Charts")
                st.caption(f"Showing {period} price history for top {n} indices by performance")

                for _, row in top5.iterrows():
                    idx_name = row["index"]
                    pch = row["percentChange"]
                    last = row["last"]
                    var = row["variation"]

                    st.markdown(f"### {idx_name}")
                    mc1, mc2 = st.columns([1, 5])
                    mc1.metric("Change", f"{pch:.2f}%", f"{var:.2f}", delta_color="normal")
                    mc1.metric("Last Price", f"{last:.2f}")

                    yf_sym = INDEX_MAP.get(idx_name)
                    if yf_sym:
                        with mc2:
                            try:
                                hist = fetch_index_history(yf_sym, period=period)
                                #st.dataframe(hist)
                                if hist is not None and not hist.empty:
                                    fig = go.Figure()
                                    fig.add_trace(
                                        go.Scatter(
                                            x=hist.index,
                                            y=hist["Close"],
                                            mode="lines",
                                            name=idx_name,
                                            line=dict(color="#ebf1f1", width=3),
                                            fill="tonexty"
                                        )
                                    )

                                    y_min = hist["Close"].min()
                                    y_max = hist["Close"].max()

                                    fig.update_layout(
                                        height=350,
                                        template="plotly_dark",
                                        hovermode="x unified",
                                        margin=dict(l=10, r=10, t=10, b=10),
                                        xaxis_title=None,
                                        yaxis_title="Value",
                                    )

                                    fig.update_yaxes(
                                        range=[y_min * 0.98, y_max * 1.02],
                                        tickformat=","
                                    )

                                    st.plotly_chart(fig, use_container_width=True)
                                    # fig = go.Figure()
                                    # fig.add_trace(go.Scatter(
                                    #     x=hist.index, y=hist["Close"],
                                    #     mode="lines", name=idx_name,
                                    #     line=dict(color="#00c853", width=2),
                                    #     fill="tozeroy", fillcolor="rgba(0,200,83,0.1)"
                                    # ))
                                    # fig.update_layout(
                                    #     height=350,
                                    #     margin=dict(l=0, r=0, t=10, b=0),
                                    #     xaxis_title=None,
                                    #     yaxis_title="Value",
                                    #     hovermode="x unified",
                                    # )
                                    # st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.info("Historical data not available")
                            except Exception as e:
                                st.warning(f"Chart unavailable: {e}")
                    else:
                        with mc2:
                            st.info("Chart not available for this index")

            except Exception as e:
                st.error(f"Error fetching data: {e}")


if __name__ == "__main__":
    main()
