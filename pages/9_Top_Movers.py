import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Make sure the project root (parent of pages/) is importable so the
# reusable analysis code in last_week_data.py can be used by this page.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import last_week_data as lwd
import pages.utils.stock_utils as stock_utils


st.set_page_config(
    page_title="Top Movers",
    page_icon="📈",
    layout="wide",
)


OUTPUT_ROOT = PROJECT_ROOT / "Top_movers_output"
TICKERS_DIR = PROJECT_ROOT / "Tickers"
PERIOD_OPTIONS = list(lwd.PERIOD_LOOKBACK_SESSIONS.keys())


def list_input_excels() -> list[Path]:
    """Return the Excel files available in the Tickers folder."""
    if not TICKERS_DIR.exists():
        return []

    excels = [
        path
        for path in sorted(TICKERS_DIR.glob("*.xlsx"))
        if not path.name.startswith("~$")
    ]

    return excels


def run_output_dir(
    period_label: str,
    direction: str,
    excel_stem: str,
) -> Path:
    """Return the output folder for a given file, period and direction."""
    key = f"{period_label.replace(' ', '')}_{direction}"
    return OUTPUT_ROOT / excel_stem / key


def history_period_for(lookback_sessions: int) -> str:
    """Pick a yfinance period that holds enough history for the lookback."""
    return "2y" if lookback_sessions + 5 > 250 else "1y"


def run_analysis(
    top_n: int,
    direction: str,
    period_label: str,
    input_excel: Path,
):
    """Do the full backend run: download, rank, chart and save."""
    input_excel = Path(input_excel)
    lookback = lwd.PERIOD_LOOKBACK_SESSIONS[period_label]
    out_dir = run_output_dir(period_label, direction, input_excel.stem)
    chart_dir = out_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    # Clear charts from a previous run of the same filters.
    for existing in chart_dir.glob("*.png"):
        try:
            existing.unlink()
        except OSError:
            pass

    symbols = lwd.load_symbols(input_excel=input_excel)
    total = len(symbols)
    history_period = history_period_for(lookback)

    progress = st.progress(
        0.0,
        text=f"Downloading history for {total} symbols...",
    )

    stock_data = {}
    movements = []
    failed = []

    for position, symbol in enumerate(symbols, start=1):
        progress.progress(
            (position - 1) / total,
            text=f"[{position}/{total}] {symbol}",
        )

        data = lwd.download_stock_history(symbol, history_period)

        if data.empty:
            failed.append(symbol)
            continue

        stock_data[symbol] = data

        try:
            movement = lwd.calculate_movement(
                symbol,
                data,
                lookback,
                period_label,
            )
        except ValueError:
            failed.append(symbol)
            continue

        movements.append(movement)
        time.sleep(lwd.REQUEST_DELAY_SECONDS)

    # Filter by direction and rank the biggest movers first.
    if direction == "UP":
        candidates = [m for m in movements if m["change_pct"] > 0]
        candidates.sort(key=lambda item: item["change_pct"], reverse=True)
    else:
        candidates = [m for m in movements if m["change_pct"] < 0]
        candidates.sort(key=lambda item: item["change_pct"])

    top_stocks = candidates[:top_n]

    progress.progress(1.0, text="Creating charts...")

    for movement in top_stocks:
        lwd.create_stock_chart(
            movement["symbol"],
            stock_data[movement["symbol"]],
            movement,
            chart_dir=chart_dir,
        )

    result = {
        "created_at": datetime.now().astimezone().isoformat(),
        "period_label": period_label,
        "lookback_sessions": lookback,
        "direction_filter": direction,
        "top_n": top_n,
        "total_symbols": total,
        "total_stocks_analyzed": len(movements),
        "failed_count": len(failed),
        "failed_symbols": failed,
        "top_stocks": top_stocks,
    }

    with (out_dir / "top_movers.json").open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    if top_stocks:
        pd.DataFrame(top_stocks).to_excel(
            out_dir / "top_movers.xlsx",
            index=False,
        )

    progress.empty()

    return result, out_dir


st.title("📈 Top Movers Chart Generator")
st.caption(
    "Scan the NSE symbol list, rank the biggest movers for the chosen "
    "period and direction, then build and save candlestick charts."
)

excel_files = list_input_excels()

default_excel_index = 0
if lwd.INPUT_EXCEL in excel_files:
    default_excel_index = excel_files.index(lwd.INPUT_EXCEL)

col_file, col_top_n, col_direction, col_period = st.columns([2, 1, 1, 1])

with col_file:
    if excel_files:
        input_excel = st.selectbox(
            "Input Excel file",
            excel_files,
            index=default_excel_index,
            format_func=lambda path: path.name,
            help=f"Excel files from {TICKERS_DIR}",
        )
    else:
        input_excel = lwd.INPUT_EXCEL
        st.warning(f"No Excel files found in {TICKERS_DIR}")

with col_top_n:
    top_n = st.number_input(
        "Top charts",
        min_value=1,
        max_value=100,
        value=lwd.TOP_N,
        step=1,
    )

with col_direction:
    direction = st.radio(
        "Direction",
        ["UP", "DOWN"],
        horizontal=True,
    )

with col_period:
    period_label = st.selectbox(
        "Time period",
        PERIOD_OPTIONS,
        index=0,
    )

generate = st.button(
    "🚀 Generate & Save Charts",
    type="primary",
    use_container_width=True,
)

if generate:
    try:
        result, out_dir = run_analysis(
            int(top_n),
            direction,
            period_label,
            input_excel,
        )
        st.success(
            f"Analyzed {result['total_stocks_analyzed']} stocks and "
            f"saved {len(result['top_stocks'])} charts to {out_dir}"
        )
    except Exception as error:
        st.error(f"Run failed: {error}")

st.markdown("---")

out_dir = run_output_dir(period_label, direction, input_excel.stem)
chart_dir = out_dir / "charts"
json_path = out_dir / "top_movers.json"

st.subheader(f"Top {int(top_n)} {direction} movers — {period_label}")

if json_path.exists():
    with json_path.open(encoding="utf-8") as file:
        saved = json.load(file)

    top_stocks = saved.get("top_stocks", [])

    if top_stocks:
        table = pd.DataFrame(top_stocks)
        table = table[
            [
                "symbol",
                "period_start",
                "period_end",
                "previous_close",
                "latest_close",
                "change_pct",
                "direction",
            ]
        ]

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(f"📂 Charts saved in: `{chart_dir}`")

        for row in top_stocks:
            symbol = row["symbol"]
            chart_path = chart_dir / f"{symbol}.png"
            screener_url = stock_utils.screener_company_url(symbol)

            st.markdown(
                f"### {symbol} — {row['change_pct']:+.2f}% "
                f"([{row['direction']}]({screener_url}))"
            )

            if chart_path.exists():
                st.image(str(chart_path), use_container_width=True)
            else:
                st.warning("Chart file missing for this stock.")
    else:
        st.info("No stocks matched the selected direction.")
else:
    st.info(
        "No results yet. Choose your filters and click "
        "**Generate & Save Charts**."
    )

st.markdown("---")
st.caption(
    "Data: Yahoo Finance | Charts: mplfinance | "
    "Analysis: last_week_data.py"
)
