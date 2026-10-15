
import json
import re
import time
from datetime import datetime
from pathlib import Path

import mplfinance as mpf
import pandas as pd
import yfinance as yf


# =========================================================
# Configuration
# =========================================================

INPUT_EXCEL = Path( r"C:\Users\aysharma\Desktop\Self_v1\Agent_on_finance_1\Trading_platform\Tickers\Tickers_nifty_500.xlsx")
#C:\Users\aysharma\Desktop\Self_v1\Agent_on_finance_1\Trading_platform\Tickers\Tickers_nifty_500.xlsx
#r"C:\Users\aysharma\Desktop\Self_v1\Agent_on_finance_1\Trading_platform\Tickers\ipo_symbols_till_9_oct_2026.xlsx"
INPUT_SHEET = 0
SYMBOL_COLUMN = "Symbol"

OUTPUT_DIR = Path(r"C:\Users\aysharma\Desktop\Self_v1\Agent_on_finance_1\Trading_platform\LAst_week_stocks_hist")
HISTORY_EXCEL = OUTPUT_DIR / "stock_historical_data.xlsx"
MOVEMENT_JSON = OUTPUT_DIR / "weekly_stock_movement.json"
CHART_DIR = OUTPUT_DIR / "charts"

HISTORY_PERIOD = "1y"
TOP_N = 10
CHART_PERIOD_DAYS = 120

# Trading sessions to look back for each selectable period.
# 5 sessions is one trading week, 21 a month, 252 a year.
PERIOD_LOOKBACK_SESSIONS = {
    "1 Week": 5,
    "1 Month": 21,
    "2 Months": 42,
    "6 Months": 126,
    "1 Year": 252,
}

DEFAULT_PERIOD = "1 Week"

# Use ".NS" for NSE stocks and ".BO" for BSE stocks.
DEFAULT_EXCHANGE_SUFFIX = ".NS"

REQUEST_DELAY_SECONDS = 0.2


# =========================================================
# Symbol helpers
# =========================================================

def normalize_symbol(symbol: str) -> str:
    """Normalize a symbol for Yahoo Finance."""
    symbol = str(symbol).strip().upper()

    if not symbol or symbol == "NAN":
        return ""

    if symbol.endswith((".NS", ".BO")):
        return symbol

    if DEFAULT_EXCHANGE_SUFFIX:
        return symbol + DEFAULT_EXCHANGE_SUFFIX

    return symbol


def get_excel_sheet_name(symbol: str, used_names: set) -> str:
    """Create a valid, unique Excel worksheet name."""
    name = re.sub(r"[\[\]:*?/\\]", "_", symbol)
    name = name[:31] or "Stock"

    original_name = name
    counter = 1

    while name.lower() in used_names:
        suffix = f"_{counter}"
        name = original_name[:31 - len(suffix)] + suffix
        counter += 1

    used_names.add(name.lower())
    return name


# =========================================================
# Read symbols from Excel
# =========================================================

def load_symbols(
    input_excel: Path = INPUT_EXCEL,
    symbol_column: str = SYMBOL_COLUMN,
) -> list[str]:
    """Read all stock symbols from the given Excel column."""
    input_excel = Path(input_excel)

    if not input_excel.exists():
        raise FileNotFoundError(
            f"Input Excel file not found: {input_excel}"
        )

    df = pd.read_excel(
        input_excel,
        sheet_name=INPUT_SHEET,
    )

    # Match the column name without case sensitivity.
    column_lookup = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    requested_column = symbol_column.strip().lower()

    if requested_column not in column_lookup:
        raise ValueError(
            f"Column '{symbol_column}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    actual_column = column_lookup[requested_column]

    symbols = [
        normalize_symbol(value)
        for value in df[actual_column].dropna()
    ]

    # Remove blanks and duplicates while preserving order.
    symbols = list(dict.fromkeys(
        symbol for symbol in symbols if symbol
    ))

    if not symbols:
        raise ValueError("No stock symbols found in the Excel file.")

    print(f"Total unique symbols loaded: {len(symbols)}")

    return symbols


# =========================================================
# Download historical stock data
# =========================================================

def download_stock_history(
    symbol: str,
    period: str = HISTORY_PERIOD,
) -> pd.DataFrame:
    """Download daily historical stock prices for the given period."""
    try:
        ticker = yf.Ticker(symbol)

        data = ticker.history(
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=True,
        )

        if data.empty:
            print(f"No historical data available: {symbol}")
            return pd.DataFrame()

        # Keep valid trading dates and OHLC values.
        data = data.copy()
        data.index = pd.to_datetime(data.index)
        data = data[~data.index.duplicated(keep="last")]
        data = data.sort_index()

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in data.columns
        ]

        if missing_columns:
            print(
                f"{symbol}: missing columns {missing_columns}"
            )
            return pd.DataFrame()

        data = data.dropna(subset=required_columns)

        if data.empty:
            return pd.DataFrame()

        print(
            f"Downloaded {symbol}: {len(data)} rows "
            f"({data.index.min().date()} to "
            f"{data.index.max().date()})"
        )

        return data

    except Exception as error:
        print(f"Download failed for {symbol}: {error}")
        return pd.DataFrame()


# =========================================================
# Calculate movement over a lookback window
# =========================================================

def calculate_movement(
    symbol: str,
    data: pd.DataFrame,
    lookback_sessions: int,
    period_label: str = DEFAULT_PERIOD,
) -> dict:
    """
    Calculate movement over the latest `lookback_sessions` trading
    sessions.

    The latest close is compared with the close that many sessions
    earlier, so a lookback of five sessions is one trading week and
    252 sessions is roughly one year.
    """
    required_observations = lookback_sessions + 1

    if data.empty or len(data) < required_observations:
        raise ValueError(
            f"{symbol} needs at least {required_observations} "
            f"daily observations."
        )

    base_position = -required_observations

    previous_close = float(data["Close"].iloc[base_position])
    latest_close = float(data["Close"].iloc[-1])

    if previous_close == 0:
        raise ValueError(
            f"{symbol} has a zero previous closing price."
        )

    change = latest_close - previous_close
    change_pct = (change / previous_close) * 100

    if change_pct > 0:
        direction = "UP"
    elif change_pct < 0:
        direction = "DOWN"
    else:
        direction = "FLAT"

    return {
        "symbol": symbol,
        "period_label": period_label,
        "period_start": str(data.index[base_position].date()),
        "period_end": str(data.index[-1].date()),
        "previous_close": round(previous_close, 4),
        "latest_close": round(latest_close, 4),
        "price_change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "absolute_movement_pct": round(abs(change_pct), 4),
        "direction": direction,
        "observations_used": lookback_sessions,
    }


def calculate_weekly_movement(
    symbol: str,
    data: pd.DataFrame,
) -> dict:
    """Backward compatible helper for the default weekly window."""
    return calculate_movement(
        symbol,
        data,
        PERIOD_LOOKBACK_SESSIONS[DEFAULT_PERIOD],
        DEFAULT_PERIOD,
    )


# =========================================================
# Create candlestick chart
# =========================================================

def create_stock_chart(
    symbol: str,
    data: pd.DataFrame,
    movement: dict,
    chart_dir: Path = CHART_DIR,
    chart_period_days: int = CHART_PERIOD_DAYS,
) -> None:
    """Create a candlestick chart with mplfinance."""
    if data.empty:
        return

    chart_dir = Path(chart_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)

    chart_data = data.tail(chart_period_days).copy()

    if chart_data.empty:
        return

    # mplfinance expects standard OHLC column names.
    chart_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    chart_data = chart_data[chart_columns]

    safe_symbol = re.sub(r"[^A-Za-z0-9_.-]", "_", symbol)
    output_path = chart_dir / f"{safe_symbol}.png"

    change_pct = movement["change_pct"]
    direction = movement["direction"]
    period_label = movement.get("period_label", "")

    title = (
        f"{symbol} | {period_label}: {change_pct:+.2f}% ({direction})"
    )

    try:
        mpf.plot(
            chart_data,
            type="candle",
            style="yahoo",
            volume=True,
            title=title,
            figsize=(14, 8),
            tight_layout=True,
            savefig={
                "fname": str(output_path),
                "dpi": 150,
                "bbox_inches": "tight",
            },
        )

        print(f"Chart saved: {output_path}")

    except Exception as error:
        print(f"Chart failed for {symbol}: {error}")


# =========================================================
# Save historical data to one workbook
# =========================================================

def save_historical_data(
    stock_data: dict[str, pd.DataFrame],
    output_dir: Path = OUTPUT_DIR,
    history_excel: Path = HISTORY_EXCEL,
) -> None:
    """Save each stock's historical prices in its own worksheet."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    used_sheet_names = set()

    with pd.ExcelWriter(
        Path(history_excel),
        engine="openpyxl",
    ) as writer:

        for symbol, data in stock_data.items():
            sheet_name = get_excel_sheet_name(
                symbol,
                used_sheet_names,
            )

            if data.empty:
                pd.DataFrame({
                    "Status": ["No historical data available"]
                }).to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                )
                continue

            # Work on a copy so the original DataFrame is unchanged.
            excel_data = data.copy()

            # Excel does not support timezone-aware datetimes.
            if isinstance(excel_data.index, pd.DatetimeIndex):
                if excel_data.index.tz is not None:
                    excel_data.index = (
                        excel_data.index.tz_localize(None)
                    )

            # Also handle timezone-aware datetime columns, if any.
            for column in excel_data.columns:
                if isinstance(
                    excel_data[column].dtype,
                    pd.DatetimeTZDtype,
                ):
                    excel_data[column] = (
                        excel_data[column].dt.tz_localize(None)
                    )

            excel_data.to_excel(
                writer,
                sheet_name=sheet_name,
                index=True,
                index_label="Date",
            )

    print(f"\nHistorical workbook saved: {history_excel}")


# =========================================================
# Save movement analysis as JSON
# =========================================================

def save_movement_json(
    movements: list[dict],
    failed_symbols: list[str],
    output_path: Path = MOVEMENT_JSON,
    top_n: int = TOP_N,
    period_label: str = DEFAULT_PERIOD,
) -> None:
    """Save all movements and rankings in a JSON file."""
    sorted_by_absolute_movement = sorted(
        movements,
        key=lambda item: item["absolute_movement_pct"],
        reverse=True,
    )

    sorted_by_positive_movement = sorted(
        movements,
        key=lambda item: item["change_pct"],
        reverse=True,
    )

    lookback = PERIOD_LOOKBACK_SESSIONS.get(period_label)

    result = {
        "created_at": datetime.now().astimezone().isoformat(),
        "period_label": period_label,
        "period_definition": (
            "Latest available close compared with the close "
            f"{lookback} trading sessions earlier."
            if lookback
            else "Latest available close compared with an earlier close."
        ),
        "ranking_definition": (
            "Absolute percentage movement, highest first."
        ),
        "total_stocks_analyzed": len(movements),
        "failed_symbols": failed_symbols,
        "highest_movement_stock": (
            sorted_by_absolute_movement[0]
            if sorted_by_absolute_movement
            else None
        ),
        "top_stocks_by_absolute_movement": (
            sorted_by_absolute_movement[:top_n]
        ),
        "top_stocks_by_positive_movement": (
            sorted_by_positive_movement[:top_n]
        ),
        "all_stocks": sorted_by_absolute_movement,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(f"Movement JSON saved: {output_path}")


# =========================================================
# Main workflow
# =========================================================

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    symbols = load_symbols()

    lookback = PERIOD_LOOKBACK_SESSIONS[DEFAULT_PERIOD]

    historical_data = {}
    movements = []
    failed_symbols = []

    for position, symbol in enumerate(symbols, start=1):
        print(
            f"\n[{position}/{len(symbols)}] Processing {symbol}"
        )

        data = download_stock_history(symbol)
        historical_data[symbol] = data

        if data.empty:
            failed_symbols.append(symbol)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        try:
            movement = calculate_movement(
                symbol,
                data,
                lookback,
                DEFAULT_PERIOD,
            )
            movements.append(movement)

            print(
                f"{symbol}: {movement['direction']} | "
                f"{movement['change_pct']:+.2f}%"
            )

        except ValueError as error:
            print(f"Movement calculation failed: {error}")
            failed_symbols.append(symbol)

        time.sleep(REQUEST_DELAY_SECONDS)

    # Save one workbook with one worksheet per symbol.
    save_historical_data(historical_data)

    # Rank stocks by absolute percentage movement.
    ranked = sorted(
        movements,
        key=lambda item: item["absolute_movement_pct"],
        reverse=True,
    )

    # Generate charts for the top N stocks by absolute movement.
    top_stocks = ranked[:TOP_N]

    for stock in top_stocks:
        symbol = stock["symbol"]
        create_stock_chart(
            symbol,
            historical_data[symbol],
            stock,
        )

    # Save movement metrics and rankings.
    save_movement_json(movements, failed_symbols)

    print("\n========== ANALYSIS COMPLETE ==========")
    print(f"Symbols read: {len(symbols)}")
    print(f"Stocks analyzed: {len(movements)}")
    print(f"Failed symbols: {len(failed_symbols)}")
    print(f"Top N charts requested: {TOP_N}")

    if ranked:
        print("\nTop stocks by absolute movement:")

        for rank, stock in enumerate(top_stocks, start=1):
            print(
                f"{rank}. {stock['symbol']}: "
                f"{stock['change_pct']:+.2f}% "
                f"({stock['direction']})"
            )


if __name__ == "__main__":
    main()
