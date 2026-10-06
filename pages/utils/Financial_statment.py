import pandas as pd
"""
order_data ={
        'stock_symbol':order["stock_symbol"],
        'stock_price':order["stock_price"],
        'timeAtOrder':order["timeAtOrder"],
        'stock_order':order["stock_order"],
        'stock_quantity': order["stock_quantity"]
    }



"""




def update_financial_statment_datadase(data : dict, balance_statment = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Database\Financial_statment.xlsx"):
    try : 
        statment_df = pd.read_excel(balance_statment, index_col='Sr.No')

        # Updating new index for dataframe 
        next_index = statment_df.index.max() + 1 if len(statment_df) > 0 else 1

        statment_df.loc[next_index] = [
            data['Date_Time'],
            data['Action'],
            data['Description'],
            data['Amount'],
            data['Final Amount']
        ]

        print(f'After Updating Statment :\n {statment_df}')
        statment_df.to_excel(balance_statment, index=True)
        print(f'Updated the statment ')

    except Exception as e :
        print(f"error : {e}")
        pass

def financial_statment(data_dict: dict, balance_statment = r"C:\Users\aysharma\Desktop\Self_v1\Trading_platform\Database\Financial_statment.xlsx"):

    # returning result of order is successfull or not
    result = False


    # Statment     
    Income_Statment = pd.read_excel(balance_statment, index_col='Sr.No')
    print(f'Statment : \n{Income_Statment}')

    # Balance 
    Latest_Balance = Income_Statment['Final Amount'].iloc[Income_Statment.index.max()-1]
    print(f"Latest Balance of Account : {Latest_Balance} \n ")

    # Order's New Amount
    amount = round(float(data_dict['stock_price'] )* float(data_dict['stock_quantity']),2)
    print(f'Order detail : \nstock price : {data_dict['stock_price']} \nstock quantity : {data_dict['stock_quantity']} \nTotal Amount : {amount} \n')
    
    if data_dict['stock_order'] == 'Buy':

        if Latest_Balance < amount :
            print(f" Balance is not sufficient")
            result = False

        elif Latest_Balance >= amount :
            try :
                new_latest_balance = Latest_Balance - amount
                print(f'New Balance : {new_latest_balance}')
                
                update_financial_statment_datadase({
                    'Date_Time':data_dict['timeAtOrder'],
                    'Action': 'Debit',
                    'Description' : f'Stock is Bought {data_dict['stock_symbol']} with Quantity {data_dict['stock_quantity']}',
                    'Amount':amount,
                    'Final Amount':new_latest_balance
                })

                result= True
            
            except Exception as e:
                pass 
    elif data_dict['stock_order'] == 'Sell':

        new_latest_balance = Latest_Balance + amount
        print(f'New Balance : {new_latest_balance}')
        
        update_financial_statment_datadase({
            'Date_Time':data_dict['timeAtOrder'],
            'Action': 'Credits',
            'Description' : f'Stock is Selled {data_dict['stock_symbol']} with Quantity {data_dict['stock_quantity']}',
            'Amount':amount,
            'Final Amount':new_latest_balance
        })

        result= True

    
    return result

def main():
    financial_statment()


if __name__ == '__main__':
    main()