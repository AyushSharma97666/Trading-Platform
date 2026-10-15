import requests
import pandas as pd
import time
import yfinance as yf
import matplotlib.pyplot as plt
import mplfinance as mpf
import datetime as dt
import os
import streamlit as st
from PIL import Image

import pages.utils.stock_utils as stock_utils


time_now = dt.datetime.now().date().strftime("%d-%B-%Y")
#folder_path = f'C:\\Users\\aysharma\\Desktop\\Self_v1\\Trading_platform\\Charts_Top5Stocks'
folder_path = os.path.join(os.getcwd(), 'Charts_Top5Stocks')

YEAR_HIGH_RATIO = 0.90

# UI data sources
SOURCE_52_WEEK_HIGH = "52 Week High (EQ)"
SOURCE_INDEX = "Index (NIFTY 500)"


# NSE "New 52 Week High/Low" page (Equity market watch)
NSE_BASE_URL = "https://www.nseindia.com"
NSE_52W_HIGH_PAGE = f"{NSE_BASE_URL}/market-data/52-week-high-equity-market"
NSE_52W_HIGH_API = f"{NSE_BASE_URL}/api/live-analysis-data-52weekhighstock"

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
    "Referer": NSE_52W_HIGH_PAGE,
}

# Column labels for the on-screen table
DISPLAY_COLUMNS = {
    "symbol": "Symbol",
    "Company": "Company",
    "series": "Series",
    "ltp": "LTP",
    "lastPrice": "Last Price",
    "prevClose": "Prev Close",
    "previousClose": "Prev Close",
    "pChange": "% Change",
    "change": "Change",
    "new52WHL": "New 52W High",
    "prev52WHL": "Prev High",
    "prevHLDate": "Prev High Date",
    "yearHigh": "52W High",
    "yearLow": "52W Low",
    "Volume_Indication": "Volume Indication",
}

# Preferred column order for the on-screen table (only present ones are kept)
DISPLAY_COLUMN_ORDER = [
    "symbol", "Company", "series", "ltp", "lastPrice", "previousClose",
    "prevClose", "pChange", "change", "new52WHL", "prev52WHL", "yearHigh",
    "yearLow", "prevHLDate", "Volume_Indication",
]


def _nse_session():
    """Create a requests session primed with the cookies NSE requires."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    # NSE answers 403 to the API unless the page cookies are present first
    session.get(NSE_52W_HIGH_PAGE, timeout=30)
    time.sleep(1)

    return session


def fetch_52_week_high_stocks(series="EQ"):
    """Fetch the NSE 52-week high list and keep only the requested series.

    The NSE page (market-data/52-week-high-equity-market) is driven by the
    live-analysis-data-52weekhighstock API. Each record carries a 'series'
    field (EQ, SM, ST, BZ, ...) which is used to keep the main board only.
    """
    session = _nse_session()

    response = session.get(NSE_52W_HIGH_API, timeout=30)
    response.raise_for_status()

    payload = response.json()
    df = pd.DataFrame(payload.get("data", []))

    if df.empty:
        print("No 52 week high data returned from NSE")
        return df

    if "series" in df.columns and series:
        df = df[df["series"] == series]

    df = df.sort_values(by="pChange", ascending=False).reset_index(drop=True)

    print(f"NSE 52 week high stocks (series={series}): {len(df)}")

    return df


def indices_data(index_name="NIFTY 500"):
    """Fetch the NSE index constituents that trade near their 52 week high.

    Uses the equity-stock-indices API and keeps only constituents whose
    previous close is within YEAR_HIGH_RATIO of the 52 week high, sorted by
    the day's percentage change.
    """
    base_url = "https://www.nseindia.com"
    api_url = f"https://www.nseindia.com/api/equity-stock-indices?index={index_name}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/market-data/live-equity-market"
    }

    session = requests.Session()

    # Get cookies
    session.get(base_url, headers=headers)
    time.sleep(2)

    # API call
    response = session.get(api_url, headers=headers)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data["data"])

    if df.empty:
        print(f"No data returned for index {index_name}")
        return df

    # the first row is the index summary itself, drop it and any blanks
    df = df[df["symbol"].notna()]
    df = df[~df["symbol"].str.contains(" ", na=False)]
    df = df.dropna(subset=["previousClose", "yearHigh"])

    # Sorting the symbols those are near one year high
    df['near_year_high'] = df['previousClose'] >= (df['yearHigh'] * YEAR_HIGH_RATIO)
    df = df[df['near_year_high'] == True]

    # Sort by percentage change
    df = df.sort_values(by="pChange", ascending=False).reset_index(drop=True)

    print(f"Index {index_name} near 52 week high stocks: {len(df)}")

    return df


def _add_company_column(stocks):
    """Add a normalized 'Company' column when a real name is available.

    The 52 week high API ships a company name while the index API only
    returns symbols, so the column is skipped rather than duplicating the
    symbol in the on-screen table.
    """
    if stocks is None or stocks.empty:
        return stocks

    if "Company" in stocks.columns:
        return stocks

    if "comapnyName" in stocks.columns:
        stocks["Company"] = stocks["comapnyName"]
    elif "meta" in stocks.columns:
        names = stocks["meta"].apply(
            lambda m: m.get("companyName") if isinstance(m, dict) else None
        )
        if names.notna().any():
            stocks["Company"] = names

    return stocks


def get_stocks(source, index_name="NIFTY 500"):
    """Return the stock list for the selected UI source."""
    if source == SOURCE_52_WEEK_HIGH:
        stocks = fetch_52_week_high_stocks(series="EQ")
    else:
        stocks = indices_data(index_name=index_name)

    return _add_company_column(stocks)


def stock_data(stock_ticker, p='3y'):
    meta = yf.Ticker(stock_ticker)
    data = meta.history(period=p)

    # adding SMA of volumne
    data['Volume_sma'] = data['Volume'].rolling(window=20).mean()

    return data


def chart_creation(stock_ticker, data, folder_path, mva_period, time_now):
    file_path = os.path.join(folder_path, f'{stock_ticker}_{time_now}.png')
    try:
        # Example EMA period
        ema_period = 200

        # Calculate EMA
        data['EMA'] = data['Close'].ewm(span=ema_period, adjust=False).mean()

        # take last 185 data points for better visualization
        data = data[-185:]

        # Create EMA plot
        ema_plot = mpf.make_addplot(data['EMA'], color='blue', width=1)

        mpf.plot(
            data,
            type='candle',
            volume=False,
            addplot=ema_plot,  # EMA added
            title=f'Chart {stock_ticker}',
            figsize=(20, 8),
            savefig=file_path
        )
        print(f'Chart save at :{file_path}')
    except Exception as e:
        print(f" error : {e}")


def main(source, index_name, folder_path, time_now, per_change_day, top_stocks=5):

    try:
        if not os.path.exists(folder_path):

            os.makedirs(folder_path)
        elif os.path.exists(folder_path):
            # List all files in the directory
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)

                # Check if it is a file (not a subdirectory)
                if os.path.isfile(file_path):
                    os.remove(file_path)  # Remove the file
                    print(f"Deleted file: {filename}")
    except Exception as e:
        print(f'error :  {e}')

    try:
        # Stock list for the selected source (52 week high EQ or an index)
        stocks = get_stocks(source, index_name=index_name)

        if stocks is None or stocks.empty:
            return stocks

        # Only keep stocks whose day change clears the selected threshold
        stocks = stocks[stocks['pChange'] >= float(per_change_day)].reset_index(drop=True)

        # Cap to the requested number of stocks
        if top_stocks > len(stocks):
            top_stocks = len(stocks)
        stocks = stocks.head(top_stocks).reset_index(drop=True)

        volumne_indication = []
        print(stocks)

        for i in range(len(stocks)):

            stock_symbol = stocks['symbol'].iloc[i] + '.NS'
            print(stock_symbol)

            try:
                if os.path.exists(folder_path):
                    # stocks history data download
                    data_download = stock_data(stock_symbol)
                    print(f"Data for {stock_symbol} downloaded successfully & len : {len(data_download)}.")

                    if data_download.empty:
                        volumne_indication.append(" No Data")
                        continue

                    #chart creation
                    chart_creation(stock_ticker=stock_symbol, data=data_download, folder_path=folder_path, mva_period=9, time_now=time_now)

                    # Volumne data returning for top 5 stocks
                    volumn_indicater = data_download[['Volume', 'Volume_sma']].iloc[-1]

                    current_volumne = float(volumn_indicater['Volume'])

                    current_volumne_sma = float(volumn_indicater['Volume_sma'])

                    print(f"Current Volumne : {current_volumne} & Current Volumne SMA : {current_volumne_sma}")

                    if current_volumne > current_volumne_sma:
                        volumne_indication.append(" Above Average Volumne")
                    elif current_volumne < current_volumne_sma:
                        volumne_indication.append(" Below Average Volumne")
                    else:
                        volumne_indication.append(" Average Volumne")

                    print(f"Volumne Indication : {volumne_indication[-1]}")

            except Exception as e:
                print(f'errror : {e}')
                volumne_indication.append(" N/A")

        # Adding volumne indication to dataframe
        if len(volumne_indication) == len(stocks):
            stocks['Volume_Indication'] = volumne_indication

        # Top stocks to show on screen
        return stocks

    except Exception as e:
        print(f"error : {e}")
        return pd.DataFrame()


def _stock_detail_text(row):
    """Build the one-line price/change detail shown under each chart."""
    parts = []

    if pd.notna(row.get("pChange")):
        parts.append(f"{row['pChange']:.2f}%")

    price = row.get("ltp", row.get("lastPrice"))
    if pd.notna(price):
        parts.append(f"Price: {price}")

    if pd.notna(row.get("new52WHL")):
        parts.append(f"52W High: {row['new52WHL']}")
    if pd.notna(row.get("prev52WHL")):
        parts.append(f"Prev High: {row['prev52WHL']}")
    if pd.notna(row.get("yearHigh")):
        parts.append(f"52W High: {row['yearHigh']}")

    return " | ".join(parts)


if __name__ == '__main__':
    st.set_page_config(
    page_title="Top Stocks",
    page_icon="Top Stocks",
    layout="wide",

    )

    st.title('Top Stocks')

    st.write("Charts of top stocks, sorted by highest percentage change")

    source = st.radio(
        "Select Data Source",
        [SOURCE_52_WEEK_HIGH, SOURCE_INDEX],
        index=0,
        horizontal=True,
        key="data_source",
    )

    index_name = "NIFTY 500"
    if source == SOURCE_INDEX:
        index_name = st.selectbox(
            "Select Index",
            ["NIFTY 500", "NIFTY PHARMA", "NIFTY METAL"],
            index=0,
            key="index_selection",
        )
        st.caption(
            "Stocks near their 52 week high from the selected index "
            "(previous close within 90% of the 52 week high). Charts are drawn from Yahoo Finance history."
        )
    else:
        st.caption(
            "Stocks hitting a new 52 week high on NSE (Series EQ / main board only). "
            "Charts are drawn from Yahoo Finance history."
        )

    per_change_day = st.selectbox("Percentage Change Day", [0, 1, 2, 3], index=0, key="per_change_day")

    top_stocks = st.selectbox("Number of Stocks", [5, 10, 15, 25], index=0, key="top_stocks")

    if st.button("Show Top Stocks"):
        try:
            top5Stocks = main(source, index_name, folder_path, time_now, per_change_day, top_stocks)

            if top5Stocks is None or top5Stocks.empty:
                st.warning("No stocks matched the selected filter.")
                st.info("Tip: lower the 'Percentage Change Day' filter to include more stocks.")
            else:
                display_cols = [c for c in DISPLAY_COLUMN_ORDER if c in top5Stocks.columns]
                display_df = top5Stocks[display_cols].rename(columns=DISPLAY_COLUMNS)
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                out_folder = folder_path
                rows = top5Stocks.to_dict('records')

                source_label = source

                rows_needed = (len(rows) + 1) // 2
                for row_idx in range(rows_needed):
                    cols = st.columns(2)
                    for col_idx in range(2):
                        stock_idx = row_idx * 2 + col_idx
                        if stock_idx >= len(rows):
                            break

                        row = rows[stock_idx]
                        symbol = row['symbol']
                        chart_path = os.path.join(out_folder, f'{symbol}.NS_{time_now}.png')

                        with cols[col_idx]:
                            if os.path.exists(chart_path):
                                image = Image.open(chart_path)
                                url = stock_utils.screener_company_url(symbol)
                                st.subheader(f"{symbol} - {source_label}")
                                st.write(f"{row.get('Company', symbol)}")
                                st.write(_stock_detail_text(row))
                                st.write(f"Volume: {row.get('Volume_Indication', '')}")
                                st.write(f"link:- {url} ")
                                st.image(image, caption=f"{symbol}.NS", width="content")
                            else:
                                st.warning(f"Chart not available for {symbol}")
        except Exception as e:
            print(f"error : {e}")
            st.error(f"Error: {e}")

    print(f"##################################################################")
