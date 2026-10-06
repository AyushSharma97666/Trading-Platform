    
import yfinance as yf
import datetime as dt 

def stock_price_download(stock_symbol):

    stock_price_data = yf.download(tickers=stock_symbol, interval='5m').reset_index()
            
    # Flatten multiindex columns
    stock_price_data.columns = [col[1] if col[0] ==' ' else col[0] for col in stock_price_data.columns]

    # Convert the timeZone
    if stock_price_data['Datetime'].dt.tz is None:
        stock_price_data['Datetime'] = stock_price_data['Datetime'].dt.tz_localize('UTC')

    stock_price_data['Datetime'] = stock_price_data['Datetime'].dt.tz_convert('Asia/Kolkata')

    stock_price_data['Datetime'] = stock_price_data['Datetime'].dt.tz_localize(None)

    return stock_price_data