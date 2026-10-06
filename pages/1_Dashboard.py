import streamlit as st
import pandas as pd
import datetime as dt 
from pages.utils.Stock_price import stock_price_download
import os 


#excel_file = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Database\Order_traction.xlsx"
excel_file = os.path.join(os.getcwd(),'Database', 'Order_traction.xlsx' )
#portfolio_excel_file = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Database\Dashboard.xlsx"
portfolio_excel_file = os.path.join(os.getcwd(), 'Database', 'Dashboard.xlsx')



def portfolio_creation(df):

    try:
        latest_stock_price = []
        total_Investments = []
        total_current_investments = []

        for i in range(len(df)):
            symbol = df['stock_symbol'].iloc[i]

            # download latest stock data
            data = stock_price_download(symbol)

            last_row = data.iloc[-1]

            # latest price
            latest_stock_price.append(round(last_row['Close'],2))

            # total investment (buy price * quantity)
            totalInvestment = round(
                df['stock_price'].iloc[i] * df['stock_quantity'].iloc[i], 2
            )
            total_Investments.append(totalInvestment)

            # current investment (current price * quantity)
            total_current_investment = round(
                last_row['Close'] * df['stock_quantity'].iloc[i], 2
            )
            total_current_investments.append(total_current_investment)

        df['Latest_stock_price'] = latest_stock_price
        df['total_investment'] = total_Investments
        df['total_current_investment'] = total_current_investments

        df['percentage_changes'] = ((df['Latest_stock_price'] - df['stock_price'])/df['stock_price']) * 100


        df = df[[ 'stock_symbol', 'stock_price', 'stock_quantity', 'Latest_stock_price','percentage_changes', 'total_investment', 'total_current_investment']]
        
        return df 

    except Exception as e:
        print("Error in portfolio_creation:", e)


def get_portfolio_kpis(df):
    # Calculate the sums from the dataframe
    total_investment = df['total_investment'].sum()
    current_total_value = df['total_current_investment'].sum()
    
    # It's usually helpful to include Profit/Loss as well
    total_p_l = current_total_value - total_investment
    p_l_percentage = (total_p_l / total_investment * 100) if total_investment != 0 else 0

    # Create the dictionary
    kpi_dict = {
        "total_investment": round(total_investment, 2),
        "current_total_value": round(current_total_value, 2),
        "total_p_l": round(total_p_l, 2),
        "p_l_percentage": f"{round(p_l_percentage, 2)}%"
    }
    
    return kpi_dict


def rename_columns(df):
    return df.rename(columns={
    'stock_symbol': 'Symbol',
    'stock_price': 'Price',
    'stock_quantity': 'Quantity',
    'Latest_stock_price': 'LTP',
    'percentage_changes': 'Percentage Changes',
    'total_investment': 'Investment',
    'total_current_investment': 'NowInvestment'
 })


def refereshing_dashboard(portfolio_excel_file, excel_file):
    
    try:        
        # Loading Data from Database
        portfolio_excel_file = pd.read_excel(portfolio_excel_file, index_col='Sr.No')

        if len(portfolio_excel_file) > 1:
            # Getting last updated time
            LastUpdatedTime = portfolio_excel_file['LastUpdated'].unique()[0]

            formate_dateTime = '%d-%m-%Y %H:%M:%S'

            # convert string from excel to datetime
            last_Update = dt.datetime.strptime(LastUpdatedTime, formate_dateTime)
        else :
            return True
        

        #--------
        # current time
        order_transcation = pd.read_excel(excel_file)

        order_transcation_last_trader = order_transcation['timeAtOrder'].iloc[order_transcation.index.max()]

        current_time = dt.datetime.strptime(order_transcation_last_trader, formate_dateTime)
        print(f"Last Updated time {last_Update} & {type(last_Update)}")
        print(f"Last Order time {current_time} & {type(current_time)}")

        if current_time > last_Update:
            
            print("we can update database as new transactions are there")
            return True
        else:
            print("no new transactions are found")

            return False

    except Exception as e:
        pass
        return False


def giving_current_time_df(df):

    if 'LastUpdated' in df.columns :
        df['LastUpdated'] = str(dt.datetime.now())
        df['LastUpdated'] = pd.to_datetime(df['LastUpdated']).dt.strftime('%d-%m-%Y %H:%M:%S')
    else :
        df['LastUpdated'] = str(dt.datetime.now())
        df['LastUpdated'] = pd.to_datetime(df['LastUpdated']).dt.strftime('%d-%m-%Y %H:%M:%S')

    return df 


def Dashboard(excel_file= excel_file, portfolio_excel_file=portfolio_excel_file):
    

    df = pd.read_excel(excel_file)

    try:
        
        if len(df)>= 1:
            for i in range(0,len(df)):
                portfolio_df = pd.read_excel(portfolio_excel_file, index_col='Sr.No')
                print(f"{i} = {len(portfolio_df)}\n")
                print(f"{df.iloc[i]}")
                if df.iloc[i]['stock_symbol'] in portfolio_df['stock_symbol'].unique():
                    print(f"{df.iloc[i]['stock_symbol']}  and order :{df.iloc[i]['stock_order']} ")

                    prev_data = portfolio_df[portfolio_df['stock_symbol'] == df.iloc[i]['stock_symbol']].iloc[0]
                    sr_no = prev_data.name
                    #print(prev_data)

                    # Previous Data 
                    prev_quantity = prev_data['stock_quantity']
                    prev_price = prev_data['stock_price']
                    print(f"prev-quantity & Price: {prev_quantity} & {prev_price}")

                    # # New Data
                    new_quantity = df.iloc[i]['stock_quantity']
                    new_price = df.iloc[i]['stock_price']
                    print(f"New quantity to add : {new_quantity} & {new_price}")
                    
                    
                    if df.iloc[i]['stock_order']== 'Buy':
                        
                        # Final Data 
                        final_quantity = prev_quantity + new_quantity
                        final_price = round(((new_price * new_quantity) + (prev_price * prev_quantity))/ (final_quantity),2)
                        print(f"Final price and quantity : {final_quantity} & {final_price}")
                        
                        portfolio_df.loc[sr_no, ['stock_price', 'stock_quantity']]={'stock_price': final_price, 'stock_quantity' : final_quantity}
                        print(f"Portfolio Dataframe :\n{portfolio_df}\n")

                        # Added current price in portfolio Database
                        # portfolio_df = giving_current_time_df(portfolio_df)

                        # Saving portfolio into excel 
                        portfolio_df.to_excel(portfolio_excel_file,index= True)

                    elif df.iloc[i]['stock_order']== 'Sell':

                        # Final Data 
                        final_quantity = prev_quantity - new_quantity
                        if final_quantity > 0:

                            print(f"Final quantity : {final_quantity}")
                            portfolio_df.loc[sr_no, ['stock_quantity']]={'stock_quantity' : final_quantity}
                            print(f"Portfolio Dataframe :\n{portfolio_df}\n")

                            # Added current price in portfolio Database
                            # portfolio_df = giving_current_time_df(portfolio_df)

                            # Saving portfolio into excel 
                            portfolio_df.to_excel(portfolio_excel_file,index= True)

                        elif final_quantity == 0 :
                            portfolio_df = portfolio_df.drop(sr_no)

                            # Saving portfolio into excel 
                            portfolio_df.to_excel(portfolio_excel_file,index= True)
                            print(f"After all stocks are selled Portfolio Dataframe :\n{portfolio_df}\n")

                            pass
                        
                        elif final_quantity < 0 :
                            print(f" quantity gone below zero")
                            pass

                        
                        portfolio_df.to_excel(portfolio_excel_file,index= True)


                else:
                    
                    # Updating new index for dataframe 
                    next_index = portfolio_df.index.max() + 1 if len(portfolio_df) > 0 else 1
                    print(f"Adding new Stock in Dashboard at Sr.No: {next_index}")
                    print(f"{portfolio_df}")
                    portfolio_df.loc[next_index] = [
                        df.iloc[i]['stock_symbol'],
                        df.iloc[i]['stock_price'],
                        df.iloc[i]['stock_quantity'],
                        dt.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                    ]
                        
                    print(f"Added Portfolio row is :\n{portfolio_df.loc[next_index]}")

                    # Added current lastUpdated time in portfolio Database
                    portfolio_df = giving_current_time_df(portfolio_df)

                    # Saving portfolio into excel 
                    portfolio_df.to_excel(portfolio_excel_file,index= True)
                    print(f"portfolio have the new stock entery : {df.iloc[i]['stock_symbol']} \nDataframe :\n {portfolio_df}")
                    print("--------")

                print("#########################################################")

            return portfolio_df
        else:
            return None
    

    except Exception as e:
        return e
    

def clear_dashboard(portfolio_excel_file=portfolio_excel_file):

    df_dash_clear = pd.read_excel(portfolio_excel_file)

    df_dash_clear = df_dash_clear.drop(df_dash_clear.index)
    df_dash_clear = df_dash_clear.set_index('Sr.No')
    print(df_dash_clear)
    df_dash_clear.to_excel(portfolio_excel_file,index=True)


if __name__ =='__main__':


    st.write("# 📊 Dashboard")

    st.markdown("""
    View and monitor your **portfolio data, stock performance, and trading activity** in one place.  
    Use the dashboard to quickly load or refresh the latest trading information.
    """)

    if st.button("Run"):

        if refereshing_dashboard(portfolio_excel_file, excel_file):
            

            clear_dashboard(portfolio_excel_file)
            # Dataframe transformation for dashboard
            
            df_dash = Dashboard()
           


            if df_dash is not None:
                # Portfolio creation
                df_dash= portfolio_creation(df_dash)

                # KPIs Calculation 
                kpi_dict = get_portfolio_kpis(df_dash)

                # renaming columns
                df_dash = rename_columns(df_dash)


                col_k1, col_k2, col_k3, col_k4 = st.columns([1,1,1,1])

                with col_k1:
                    st.metric(label="Total Investment", value=kpi_dict['total_investment']) #, delta="1.2 °F"
                
                with col_k2:
                    st.metric(label="Total Current Value", value=kpi_dict['current_total_value']) #, delta="1.2 °F"

                with col_k3:
                    st.metric(label="Total Current Value", value=kpi_dict['total_p_l'], delta=kpi_dict['p_l_percentage'])




                st.dataframe(data=df_dash, hide_index=True)
            else:
                st.write("No Trade has be taken Yet")
        else:
            # Dataframe transformation for dashboard
            df_dash=pd.read_excel(portfolio_excel_file)
            df_dash = portfolio_creation(df_dash)
            df_dash = rename_columns(df_dash)
            st.dataframe(data=df_dash, hide_index=True)
    

    if st.button("Clear Dashboard"):
        clear_dashboard()



       




                        


