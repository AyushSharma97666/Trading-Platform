import streamlit as st
import pandas as pd 
import yfinance as yf
import datetime as dt
from pages.utils.Stock_price import stock_price_download
from pages.utils.Financial_statment import financial_statment
import os


#ticker_excel = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Tickers\Tickers_nifty_500.xlsx"
ticker_excel = os.path.join(os.getcwd(),'Tickers', 'Tickers_nifty_500.xlsx')
#Order_traction = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Database\Order_traction.xlsx"
Order_traction = os.path.join(os.getcwd(),'Database', 'Order_traction.xlsx')

if 'order_type' not in st.session_state:
    st.session_state.order_type = None
if 'show_data' not in st.session_state:
    st.session_state.show_data = None
if 'order_data' not in st.session_state:
    st.session_state.order_data = None


def Buy_Sell_Stock(order):
    
    
    order_data ={
        'stock_symbol':order["stock_symbol"],
        'stock_price':order["stock_price"],
        'timeAtOrder':order["timeAtOrder"],
        'stock_order':order["stock_order"],
        'stock_quantity': order["stock_quantity"]
    }

    # New Data 
    order_df = pd.DataFrame([order_data])
    #order_df['timeAtOrder'] =  pd.to_datetime(order_df['timeAtOrder']).dt.floor('min')
    order_df['timeAtOrder'] = pd.to_datetime(order_df['timeAtOrder']).dt.strftime('%d-%m-%Y %H:%M:%S')
    order_df = order_df.set_index('timeAtOrder')

    # Previous data from Database
    previous_order_data = pd.read_excel(Order_traction,index_col='timeAtOrder')

    # Updating Database
    new_order_data = pd.concat([previous_order_data, order_df])
    new_order_data.to_excel(Order_traction, index=True)


def main_page():
    

    # Streamlit page layout setup
    st.set_page_config(layout='wide')

    # Page title
    st.title('Trading Section')

    # columns are set
    col1, col2, col3 = st.columns([3, 2, 3])

    # stock symbol input
    with col1:
        stock_symbol = st.text_input(
            'Stock Symbol', 
            placeholder="Enter Stock Symbol")
        
        print(f"Input Stock Name : {stock_symbol}")
        
    # with col2 :
    #     stock_quantity = st.text_input('Quantity')

    # Search Stock Price
    if st.button("Search"):
        stock_list = pd.read_excel(ticker_excel)
        if stock_symbol in list(stock_list['Ticker']):
            try :
                # Download stock Price
                stock_price_data = stock_price_download(stock_symbol)
                
                st.write(f"### Stock Prize : {round(float(stock_price_data['Close'].iloc[-1]),2)}")
            except Exception as e:
                st.write(f"error : {e}")
        else:
            st.write(f" {stock_symbol} Stock is not present in list")


    st.write("---------------------------------------------------------------------------------------")

    # columns are set
    col21, col22, col23 = st.columns([3, 2, 3])
    with col21:
        # Quantity input 
        stock_quantity = st.text_input(
            'Quantity',
            placeholder="Enter the Quantity of Stock")

        print(f'Input Stock Quantity : {stock_quantity}')

    col11,_,col12,col13 =st.columns([1,0.5,1,10])

    with col11:
        
        # button for buying stock
        if st.button('Buy'):
            # Download stock Price
            stock_price_data = stock_price_download(stock_symbol)
            stock_price_data = round(float(stock_price_data['Close'].iloc[-1]),2)

            order_type="Buy"
            st.session_state.order_data = {
            'stock_symbol':stock_symbol,
            'stock_price':str(stock_price_data),
            'timeAtOrder': str(dt.datetime.now()),
            'stock_order':order_type,
            'stock_quantity':stock_quantity
            }
            print(f'Order detail : {st.session_state.order_data}')

            try:
                if financial_statment(st.session_state.order_data) == True:
                    Buy_Sell_Stock(st.session_state.order_data)
                elif financial_statment(st.session_state.order_data) == False:
                    st.write("Insufficient funds to complete the purchase.")
            except Exception as e:
                print(f" Error : {e}")
                pass

    
    with col12:
        # button for selling stock
        if st.button('Sell'):
            # Download stock Price
            stock_price_data = stock_price_download(stock_symbol)
            stock_price_data = round(float(stock_price_data['Close'].iloc[-1]),2)


            order_type="Sell"
            
            st.session_state.order_data = {
            'stock_symbol':stock_symbol,
            'stock_price':str(stock_price_data),
            'timeAtOrder': str(dt.datetime.now()),
            'stock_order': order_type,
            'stock_quantity':stock_quantity
            }
            print(f'Order detail : {st.session_state.order_data}')
            try:
                if financial_statment(st.session_state.order_data) == True:
                    Buy_Sell_Stock(st.session_state.order_data)
                elif financial_statment(st.session_state.order_data) == False:
                    st.write("Insufficient funds to complete the purchase.")
            except Exception as e:
                print(f" Error : {e}")
                pass
    

    # Order details shown on frontend 
    order_data_to_show = st.session_state.order_data

    # Showing Order details 
    if st.session_state.order_data is not None :
        st.write('# Order Details :')
        st.write(f'### Stock is {'Bought ' if order_data_to_show['stock_order'] == 'Buy'else 'Selled'}')
        st.write(f'Stock Name : {order_data_to_show['stock_symbol']}')
        st.write(f'Price : {order_data_to_show['stock_price']}')
        st.write(f'Quantity : {order_data_to_show['stock_quantity']}')
        st.write(f'Time of Order : {order_data_to_show['timeAtOrder']}')
    else:
        pass

    print('#########################################################################################################################################')
    

def main():
    main_page()


if __name__ =='__main__':
    main()



    