import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import os 


folder_path = os.path.join(os.getcwd(), 'Database', 'Financial_statment.xlsx')
image_path = os.path.join(os.getcwd(), 'Fund_Flow', 'Fund_Statement_Chart.png')


def load_data():
    df = pd.read_excel(folder_path)
    return df

def create_chart(df):

    df['Date_Time'] = pd.to_datetime(df['Date_Time']).dt.date
    df['Final Amount'] = df['Final Amount'].astype(float)

    plt.figure(figsize=(10, 5))
    plt.plot(df['Date_Time'], df['Final Amount'], marker='o')
    plt.xlabel('Date')
    plt.ylabel('Final Amount')
    plt.title('Fund Statement')
    plt.xticks(rotation=45)
    plt.tight_layout()
    #st.pyplot(plt)

    plt.savefig(image_path)
    
def main():
    st.title("Fund Statement")
    
    if st.button("Load Data"):
        df = load_data()
        st.write(df)
        create_chart(df)
    
        st.image(image_path, caption='Fund Statement Chart')


if __name__ == "__main__":  
    main()


