import os
from matplotlib import ticker
import yfinance as yf
import matplotlib.pyplot as plt
import glob
import mplfinance as mpf



def chart_creation(stock_ticker, data, folder_path, time_now):
    file_path = f'{folder_path}\\{stock_ticker}_{time_now}.png'
    try : 



        mpf.plot(
            data,
            type='candle',
            volume=False,
            title=f'Chart {stock_ticker}',
            figsize=(20,8),
            savefig=file_path
        )
        print(f'Chart save at :{file_path}')
    except Exception as e:
        print(f" error : {e}")

def create_stock_charts(
        stock_list,
        output_folder=r"C:\Users\aysharma\Desktop\Self_v1\LatestPIPO_Tracker\latest_ipo_stocks_charts",
        period="6mo",
        interval="1d"
    ):
    """
    Download stock data and save charts.

    Parameters
    ----------
    stock_list : list
        List of stock symbols
        Example: ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']

    output_folder : str
        Folder where charts will be saved

    period : str
        yfinance period
        Example: '1mo', '3mo', '6mo', '1y', '5y'

    interval : str
        Example: '1d', '1wk', '1mo'
    """

    os.makedirs(output_folder, exist_ok=True)

    # Remove existing chart files
    for file in glob.glob(os.path.join(output_folder, "*.png")):
        try:
            os.remove(file)
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Unable to delete {file}: {e}")

    # Create new charts
    for symbol in stock_list:
        try:
            print(f"Downloading {symbol}...")

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            # file path for saving the chart
            file_path = f'{output_folder}\\{symbol}.png'

            try:
                mpf.plot(
                    df,
                    type='candle',
                    volume=False,
                    title=f'Chart {symbol}',
                    figsize=(20,8),
                    savefig=file_path
                )
            except Exception as e:
                print(f"Error plotting chart for {symbol}: {e}")

            print(f'Chart save at :{file_path}')

        except Exception as e:
            print(f"Error for {symbol}: {e}")


if __name__ == '__main__':
    stocks = [
            "BAGMANE.RR.NS",
        "KISSHT.NS",
        "CITIUSINVT.NS",
        "OMPOWER.NS",
        "AMIRCHAND.NS",
            "POWERICA.NS",
        "SAIPARENT.NS",
        "CMPDI.NS",
        "GSPCROP.NS",
        "RIIT.NS",
        "INNOVISION.NS",
        "RSL.NS",
        "SEDEMAC.NS",
        "OMNI.NS",
        "PNGSREVA.NS",
        "SRTL.NS",
        "CLEANMAX.NS",

        "GAUDIUMIVF.NS",
        "AYE.NS",
        "FRACTAL.NS",
        "SHADOWFAX.NS",
        "AMAGI.NS",
        "BHARATCOAL.NS"
    ]

    create_stock_charts(
        stocks,
        output_folder=r"C:\Users\aysharma\Desktop\Self_v1\LatestPIPO_Tracker\latest_ipo_stocks_charts",
        period="1y"
    )