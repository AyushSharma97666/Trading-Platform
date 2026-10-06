import streamlit as st

import requests
import pandas as pd
import logging
import os 
import datetime 

from pages.utils.logging_config import setup_logger

# ==========================================================
# LOGGER SETUP
# ==========================================================

logger = setup_logger(__name__)

def fetch_upcoming_ipos():
    url = "https://www.nseindia.com/api/ipo-current-issue"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"
    }

    session = requests.Session()

    try:
        # First request to get cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=10)

        # Actual API request
        response = session.get(url, headers=headers, timeout=10)

        # df is dataframe of upcoming IPOs
        df = pd.DataFrame()
        
        # Check for successful response (status code 200)
        if response.status_code == 200:
            data = response.json()
            print(f"API Response : {data}")

            # Check if data is not empty
            if data:
                # Convert to dataframe
                df = pd.json_normalize(data)
                df = df[df['series'] == 'EQ']
                print(f"Dataframe : {df}")

                # Select relevant columns and rename them
                df = df[['symbol', 'companyName', 'series',  'issueStartDate', 'issueEndDate', 'noOfTime']]
                df.columns = ['Symbol', 'Company Name', 'Type of IPO', 'Open Date', 'Close Date', 'Subscription'] 
                print(f"Upcoming IPOs Dataframe : {df}")
            else:
                #st.warning("No IPO data available at this time.")
                print("No IPO data available at this time.")
        else:
            #st.error(f"API request failed with status code: {response.status_code}")
            print(f"API request failed with status code: {response.status_code}")

    except requests.exceptions.Timeout:
        #st.error("Request timed out. Please try again.")
        print("Request timed out")
    except requests.exceptions.ConnectionError:
        #st.error("Connection error. Please check your internet connection.")
        print("Connection error")
    except requests.exceptions.RequestException as e:
        #st.error(f"An error occurred: {str(e)}")
        print(f"Request exception: {e}")
    except Exception as e:
        #st.error(f"Unexpected error: {str(e)}")
        print(f"Unexpected error: {e}")
    
    return df




def main_page():
    st.set_page_config(layout='wide')
    st.title('Upcoming IPOs')

    if st.button("Fetch Upcoming IPOs"):
        df_upcoming_ipos = fetch_upcoming_ipos()
        st.dataframe(df_upcoming_ipos)



if __name__ == '__main__':
    main_page()
