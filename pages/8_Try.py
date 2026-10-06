import io
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import pages.utils.stock_utils as stock_utils


# ==========================================================
# CONFIGURATION
# ==========================================================

STOCKS_SYMBOLS_EXCEL = (
    r"C:\Users\aysharma\Desktop\Self_v1"
    r"\Trading_platform\Tickers\Tickers_nifty_500.xlsx"
)

FINANCIAL_JSON_FILE = (
    r"C:\Users\aysharma\Desktop\Self_v1"
    r"\Trading_platform\Data\stocks_financial_summary.json"
)

CACHE_DAYS = 90


# ==========================================================
# LOAD SAVED JSON
# ==========================================================

def load_financial_json(
    file_path: str
) -> dict | None:
    """
    Load previously saved financial JSON.
    """

    if not os.path.exists(file_path):
        return None

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ) as error:

        print(
            f"Unable to load financial JSON: {error}"
        )

        return None


# ==========================================================
# CHECK CACHE VALIDITY
# ==========================================================

def is_cache_valid(
    financial_data: dict
) -> bool:
    """
    Check whether saved financial data
    was created within the last 90 days.
    """

    created_at = financial_data.get(
        "created_at"
    )

    if not created_at:
        return False

    try:

        created_datetime = datetime.fromisoformat(
            created_at
        )

        current_datetime = datetime.now()

        data_age = (
            current_datetime
            - created_datetime
        )

        return data_age < timedelta(
            days=CACHE_DAYS
        )

    except (
        ValueError,
        TypeError
    ):

        return False


# ==========================================================
# SAVE JSON
# ==========================================================

def save_financial_json(
    financial_data: dict,
    file_path: str
) -> None:
    """
    Save financial data to JSON file.
    """

    directory = os.path.dirname(
        file_path
    )

    if directory:

        os.makedirs(
            directory,
            exist_ok=True
        )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            financial_data,
            file,
            indent=4,
            ensure_ascii=False,
            default=str
        )


# ==========================================================
# READ STOCK SYMBOLS FROM EXCEL
# ==========================================================

def get_stock_symbols(
    excel_file: str
) -> list[str]:
    """
    Read stock symbols from Excel.
    """

    symbol_df = pd.read_excel(
        excel_file
    )

    if "Symbol" not in symbol_df.columns:

        raise ValueError(
            "Excel file must contain a 'Symbol' column."
        )

    symbols = (
        symbol_df["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    return symbols


# ==========================================================
# FETCH FINANCIAL DATA
# ==========================================================

def create_financial_json(
    symbol_list: list[str]
) -> dict:
    """
    Fetch financial data for all stocks.
    """

    financial_symbol_dict = {}

    for symbol in symbol_list:

        try:

            print(
                f"Fetching financial data for: {symbol}"
            )

            # --------------------------------------------------
            # Get financial data
            # --------------------------------------------------

            df_year, df_quarter = (
                stock_utils.get_financials(
                    symbol
                )
            )

            # --------------------------------------------------
            # Build financial summary
            # --------------------------------------------------

            financial_summary = (
                stock_utils.build_financial_summary(
                    df_year,
                    df_quarter
                )
            )

            financial_symbol_dict[symbol] = (
                financial_summary
            )

            print(
                f"Completed: {symbol}"
            )

        except Exception as error:

            print(
                f"Error processing {symbol}: {error}"
            )

            financial_symbol_dict[symbol] = {
                "error": str(error)
            }

    return financial_symbol_dict


# ==========================================================
# GET FINANCIAL DATA
# ==========================================================

def get_financial_data() -> tuple[dict, bool]:
    """
    Load cached financial data if it is less than 90 days old.

    Otherwise fetch fresh data and save it.

    Returns:
        financial_data
        from_cache
    """

    # ------------------------------------------------------
    # Check existing JSON
    # ------------------------------------------------------

    existing_data = load_financial_json(
        FINANCIAL_JSON_FILE
    )

    if (
        existing_data is not None
        and is_cache_valid(existing_data)
    ):

        return existing_data, True

    # ------------------------------------------------------
    # Cache does not exist or has expired
    # ------------------------------------------------------

    symbols = get_stock_symbols(
        STOCKS_SYMBOLS_EXCEL
    )

    financial_summary = create_financial_json(
        symbols
    )

    # ------------------------------------------------------
    # Add created_at
    # ------------------------------------------------------

    financial_data = {
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "data": financial_summary
    }

    # ------------------------------------------------------
    # Save JSON
    # ------------------------------------------------------

    save_financial_json(
        financial_data,
        FINANCIAL_JSON_FILE
    )

    return financial_data, False


# ==========================================================
# CONVERT JSON TO DATAFRAME
# ==========================================================

def financial_json_to_dataframe(
    financial_data: dict
) -> pd.DataFrame:
    """
    Convert financial JSON into a flat table.

    Each stock becomes one row.
    Nested JSON fields become columns.
    """

    stock_data = financial_data.get(
        "data",
        {}
    )

    rows = []

    for symbol, summary in stock_data.items():

        # --------------------------------------------------
        # Start row with stock symbol
        # --------------------------------------------------

        row = {
            "Symbol": symbol
        }

        # --------------------------------------------------
        # Handle error records
        # --------------------------------------------------

        if isinstance(summary, dict):

            flattened_data = pd.json_normalize(
                summary,
                sep="_"
            )

            if not flattened_data.empty:

                row.update(
                    flattened_data.iloc[0].to_dict()
                )

        else:

            row["Financial Summary"] = str(
                summary
            )

        rows.append(row)

    return pd.DataFrame(rows)


# ==========================================================
# DATAFRAME TO EXCEL
# ==========================================================

def dataframe_to_excel(
    df: pd.DataFrame
) -> bytes:
    """
    Convert DataFrame to Excel bytes.
    """

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Financial Summary"
        )

    return output.getvalue()


# ==========================================================
# DATAFRAME TO CSV
# ==========================================================

def dataframe_to_csv(
    df: pd.DataFrame
) -> bytes:
    """
    Convert DataFrame to CSV bytes.
    """

    return df.to_csv(
        index=False
    ).encode("utf-8")


# ==========================================================
# STREAMLIT UI
# ==========================================================

def main():

    st.title(
        "📊 NIFTY 500 Financial Summary"
    )

    st.write(
        "Generate, view and download financial "
        "summary data for all stocks."
    )

    # ======================================================
    # GENERATE / LOAD BUTTON
    # ======================================================

    if st.button(
        "Generate Financial Summary",
        type="primary"
    ):

        try:

            # --------------------------------------------------
            # Fetch or load data
            # --------------------------------------------------

            with st.spinner(
                "Checking financial data..."
            ):

                financial_data, from_cache = (
                    get_financial_data()
                )

            # --------------------------------------------------
            # Created date
            # --------------------------------------------------

            created_at = financial_data.get(
                "created_at"
            )

            # --------------------------------------------------
            # Cache message
            # --------------------------------------------------

            if from_cache:

                st.success(
                    "Existing financial data is less than "
                    "90 days old. Using the saved data."
                )

            else:

                st.success(
                    "Financial data was generated "
                    "and saved successfully."
                )

            # --------------------------------------------------
            # Display creation date
            # --------------------------------------------------

            st.info(
                f"Data created at: {created_at}"
            )

            # --------------------------------------------------
            # Get stock data
            # --------------------------------------------------

            stock_data = financial_data.get(
                "data",
                {}
            )

            st.write(
                f"Total stocks: {len(stock_data)}"
            )

            # ==================================================
            # DISPLAY JSON
            # ==================================================

            st.subheader(
                "📋 Financial Summary JSON"
            )

            for symbol, summary in stock_data.items():

                with st.expander(
                    f"📈 {symbol}"
                ):

                    st.json(
                        summary,
                        expanded=False
                    )

            # ==================================================
            # CONVERT JSON TO TABLE
            # ==================================================

            st.subheader(
                "📊 Financial Summary Table"
            )

            financial_df = (
                financial_json_to_dataframe(
                    financial_data
                )
            )

            # --------------------------------------------------
            # Display table
            # --------------------------------------------------

            st.dataframe(
                financial_df,
                width="stretch"
            )

            # ==================================================
            # DOWNLOAD FILES
            # ==================================================

            st.subheader(
                "📥 Download Financial Data"
            )

            # --------------------------------------------------
            # Create Excel
            # --------------------------------------------------

            excel_data = dataframe_to_excel(
                financial_df
            )

            # --------------------------------------------------
            # Create CSV
            # --------------------------------------------------

            csv_data = dataframe_to_csv(
                financial_df
            )

            # --------------------------------------------------
            # Download buttons
            # --------------------------------------------------

            col1, col2 = st.columns(2)

            with col1:

                st.download_button(
                    label="📊 Download Excel",
                    data=excel_data,
                    file_name=(
                        "stocks_financial_summary.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    )
                )

            with col2:

                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=(
                        "stocks_financial_summary.csv"
                    ),
                    mime="text/csv"
                )

        except Exception as error:

            st.error(
                f"Unable to process financial data: {error}"
            )

            print(
                f"Financial data error: {error}"
            )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()