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

def indices_data(index_name="NIFTY 500", top_stocks=5):

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

    # Sorting the symbols those are near one year high 
    df['near_year_high'] = df['previousClose'] >= (df['yearHigh'] * YEAR_HIGH_RATIO) 
    df = df[df['near_year_high'] == True]

    # Sort by percentage change
    df = df.sort_values(by="pChange", ascending=False)
    print(f"top_stocks: {top_stocks} length of df:{len(df)}")
    try:
        if top_stocks > len(df):
            top_stocks = len(df)
            print('length of df is greater than top_stocks')

    except Exception as e:
        print(f'Issue in the filter the index data api details')

    # df
    
    # Top gainers
    return df[["symbol", "pChange"]].head(top_stocks).reset_index(drop=True)


def stock_data(stock_ticker, p='3y' ):
    meta = yf.Ticker(stock_ticker)
    data = meta.history(period=p)

    # adding SMA of volumne
    data['Volume_sma'] = data['Volume'].rolling(window=20).mean()

    return data 

def chart_creation(stock_ticker, data, folder_path, mva_period, time_now):
    file_path = f'{folder_path}\\{stock_ticker}_{time_now}.png'
    try : 
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
            addplot=ema_plot, # EMA added
            title=f'Chart {stock_ticker}',
            figsize=(20,8),
            savefig=file_path
        )
        print(f'Chart save at :{file_path}')
    except Exception as e:
        print(f" error : {e}")


def main(index_name, folder_path, time_now, per_change_day):
    
    
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
        top5Stocks = indices_data(index_name=index_name , top_stocks=25)
        volumne_indication = []
        print(top5Stocks)

        for i in range(len(top5Stocks)):

            stock_symbol = top5Stocks['symbol'].iloc[i] + '.NS'
            print(stock_symbol)

            

            if top5Stocks['pChange'].iloc[i] >= float(per_change_day):

                try: 
                    if os.path.exists(folder_path):
                        # stocks history data download
                        data_download = stock_data(stock_symbol)
                        print(f"Data for {stock_symbol} downloaded successfully & len : {len(data_download)}.")
                        

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
                # data_stocks = stock_data_chart_Creation(stock_ticker=f'{stock_symbol}.NS')
        
        # top5Stocks = top5Stocks[top5Stocks['pChange'] >= per_change_day]
        # # Adding volumne indication to dataframe
        # top5Stocks['Volume_Indication'] = volumne_indication

        # Top 5 stocks to show on screen
        return top5Stocks
    

    except Exception as e:
        print(f"error : {e}")


if __name__ == '__main__':
    st.set_page_config(
    page_title="Top 5 Stocks",
    page_icon="Top 5 Stocks",
    layout="wide",
    
    )
    
    st.title('Top 5 Stocks')

    st.write(f"Charts of top 5 stocks with highest percentage change (greater than 3%)")

    indice = st.selectbox("Select Index", ["NIFTY 500", "NIFTY PHARMA", "NIFTY METAL"], index=0, key="index_selection")

    per_change_day = st.selectbox("Percentage Change Day", [0,1,2,3], index=0, key="per_change_day")

    if st.button("Top 5 Stocks"):
        try : 
            top5Stocks = main(indice, folder_path, time_now, per_change_day)

            st.dataframe(top5Stocks)
            out_folder = folder_path
            for i in os.listdir(out_folder):
                if i.endswith(("jpg", "jpeg", "png")):
                    image = Image.open(os.path.join(out_folder, i))
                    url = stock_utils.screener_company_url(i)
                    st.write(f"{i.split('.')[0]} - Percentage Change: {top5Stocks[top5Stocks['symbol'] == i.split('.')[0]]['pChange'].values[0]}% " )
                    st.write(f"link:-{url} ")
                    st.image(image, caption=i, width="content")
        except Exception as e:
            print(f"error : {e}")

    print(f"##################################################################")



