import logging
import time
from pathlib import Path

import mplfinance as mpf
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

import pages.utils.stock_utils as stock_utils

# curl_cffi impersonates a real Chrome TLS fingerprint, which NSE needs to
# accept the requests. Falls back to plain requests when it is not installed.
try:
    from curl_cffi import requests as nse_requests

    HAS_CURL_CFFI = True
    NSE_REQUEST_ERRORS = (
        requests.exceptions.RequestException,
        nse_requests.exceptions.RequestException,
    )
    CONNECTION_ERRORS = (
        requests.exceptions.ConnectionError,
        nse_requests.exceptions.ConnectionError,
    )
except ImportError:
    nse_requests = requests
    HAS_CURL_CFFI = False
    NSE_REQUEST_ERRORS = (requests.exceptions.RequestException,)
    CONNECTION_ERRORS = (requests.exceptions.ConnectionError,)


# =========================================================
# Configuration
# =========================================================

NSE_HOME = "https://www.nseindia.com"

INDEX_PAGE_URL = (
    "https://www.nseindia.com/market-data/live-market-indices"
)

ALL_INDICES_API = (
    "https://www.nseindia.com/api/allIndices"
)

INDEX_CONSTITUENTS_API = (
    "https://www.nseindia.com/api/equity-stock-indices"
)

CHART_FOLDER = Path(__file__).resolve().parent.parent / "charts" / "6_Sector_Indices"

REQUEST_DELAY_SECONDS = 1


# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# Create NSE session
# =========================================================

def create_nse_session():
    """
    Create an HTTP session and request the NSE homepage
    to obtain session cookies.
    """

    logger.info("Creating NSE HTTP session")

    if HAS_CURL_CFFI:
        session = nse_requests.Session(impersonate="chrome")
    else:
        session = nse_requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": INDEX_PAGE_URL,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }
    )

    response = session.get(
        NSE_HOME,
        timeout=30,
    )

    try:
        response.raise_for_status()
    except Exception as exc:
        # Attempt one more visit without raising before letting the caller
        # handle it — curl_cffi can return a response with 403 but a text body.
        raise

    logger.info(
        "NSE homepage loaded successfully. HTTP status: %s",
        response.status_code,
    )

    return session


# =========================================================
# Step 1: Read available index names
# =========================================================

def fetch_index_names(
    session: requests.Session,
) -> list[str]:
    """
    Read index names from the NSE Live Market Indices page.

    If the names are not present in the page HTML, use the
    NSE allIndices API as a fallback.
    """

    logger.info("Fetching available NSE index names")

    index_names = []

    # -----------------------------------------------------
    # Attempt 1: Parse index names from the webpage HTML
    # -----------------------------------------------------

    try:
        response = session.get(
            INDEX_PAGE_URL,
            timeout=30,
        )

        response.raise_for_status()

        logger.info(
            "NSE index page loaded. HTTP status: %s",
            response.status_code,
        )

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        # Read options from dropdowns on the page.
        for option in soup.select("select option"):
            name = option.get_text(strip=True)

            if (
                name
                and name.lower() not in {
                    "select",
                    "select index",
                    "select an index",
                }
                and name not in index_names
            ):
                index_names.append(name)

        logger.info(
            "Found %s index names in page HTML",
            len(index_names),
        )

    except NSE_REQUEST_ERRORS as exc:
        logger.warning(
            "Could not read index page HTML: %s",
            exc,
        )

    # -----------------------------------------------------
    # Attempt 2: Fallback to NSE allIndices API
    # -----------------------------------------------------

    if not index_names:
        logger.info(
            "No index names found in HTML. Trying NSE API."
        )

        try:
            response = get_with_retries(
                session,
                ALL_INDICES_API,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": INDEX_PAGE_URL,
                },
            )

            payload = response.json()

            for item in payload.get("data", []):
                name = item.get("index")

                if (
                    isinstance(name, str)
                    and name.strip()
                    and name.strip() not in index_names
                ):
                    index_names.append(name.strip())

            logger.info(
                "Found %s index names using NSE API",
                len(index_names),
            )

        except (NSE_REQUEST_ERRORS, ValueError) as exc:
            logger.error(
                "Failed to fetch constituents for %s: %s",
                index_name,
                exc,
            )

    if not index_names:
        raise RuntimeError(
            "Could not retrieve NSE index names. "
            "NSE may be blocking the request or the page "
            "structure/API may have changed."
        )

    index_names = sorted(
        set(index_names),
        key=str.casefold,
    )

    logger.info("Available index names:")

    for name in index_names:
        logger.info("  %s", name)

    return index_names


def refresh_session_cookies(session) -> None:
    """Re-hit the NSE homepage so the session cookies stay fresh."""
    try:
        session.get(NSE_HOME, timeout=30)
    except NSE_REQUEST_ERRORS as exc:
        logger.warning("Could not refresh NSE session cookies: %s", exc)


def get_with_retries(
    session,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 4,
    timeout: int = 30,
):
    """GET a URL retrying on connection resets from NSE."""
    backoff = 2

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            if HAS_CURL_CFFI:
                try:
                    response.raise_for_status()
                except Exception as exc:
                    if getattr(response, "status_code", None) in (404, 403):
                        raise
                    logger.warning("API returned non-2xx (attempt %s): %s", attempt, exc)
                    if attempt == max_retries:
                        raise
                    refresh_session_cookies(session)
                    time.sleep(backoff * attempt)
                    continue
                return response

            response.raise_for_status()
            return response
        except CONNECTION_ERRORS as exc:
            logger.warning(
                "Attempt %s/%s failed (connection): %s",
                attempt,
                max_retries,
                exc,
            )

            if attempt == max_retries:
                raise

            refresh_session_cookies(session)
            time.sleep(backoff * attempt)


# =========================================================
# Step 2: Fetch stock constituents for an index
# =========================================================

def fetch_index_constituents(
    session: requests.Session,
    index_name: str,
) -> pd.DataFrame:
    """
    Fetch stock constituents for one NSE index.
    """

    logger.info(
        "Fetching constituents for index: %s",
        index_name,
    )

    response = get_with_retries(
        session,
        INDEX_CONSTITUENTS_API,
        params={"index": index_name},
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": INDEX_PAGE_URL,
        },
    )

    payload = response.json()

    rows = payload.get("data", [])

    if not rows:
        logger.warning(
            "No constituent data returned for %s",
            index_name,
        )

        return pd.DataFrame()

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Remove rows without stock symbols.
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype("string").str.strip()

        df = df[
            df["symbol"].notna()
            & df["symbol"].ne("")
        ].copy()

        # Remove an index summary row if the API includes it.
        df = df[
            df["symbol"].str.casefold()
            != index_name.casefold()
        ].copy()

        # Remove duplicate stock symbols within this index.
        df = df.drop_duplicates(
            subset=["symbol"],
            keep="first",
        )

    # Record the source index for every constituent.
    df.insert(
        0,
        "index_name",
        index_name,
    )

    logger.info(
        "Fetched %s constituent rows for %s",
        len(df),
        index_name,
    )

    return df


# =========================================================
# Chart helpers
# =========================================================

def download_history(symbol: str, period: str = "1y") -> pd.DataFrame | None:
    """Download OHLCV history for a yfinance symbol."""
    try:
        ticker = yf.Ticker(symbol)
        return ticker.history(period=period)
    except Exception as exc:
        logger.warning("Could not download history for %s: %s", symbol, exc)
        return None


def save_stock_chart(symbol: str, data: pd.DataFrame, folder: Path) -> Path | None:
    """Save a candlestick chart with a 20-day SMA into the given folder."""
    folder.mkdir(parents=True, exist_ok=True)
    chart_path = folder / f"{symbol}.png"

    try:
        frame = data.tail(185)
        sma = frame["Close"].rolling(window=20).mean()
        add_plots = [mpf.make_addplot(sma, color="blue", width=1)]

        mpf.plot(
            frame,
            type="candle",
            volume=False,
            addplot=add_plots,
            title=symbol,
            figsize=(16, 7),
            savefig=str(chart_path),
        )

        logger.info("Chart saved at: %s", chart_path)
        return chart_path
    except Exception as exc:
        logger.warning("Could not save chart for %s: %s", symbol, exc)
        return None


def clear_charts(folder: Path) -> None:
    """Remove charts from a previous run of the same page."""
    folder.mkdir(parents=True, exist_ok=True)

    for chart in folder.glob("*.png"):
        try:
            chart.unlink()
            logger.info("Deleted chart: %s", chart.name)
        except OSError:
            pass


# =========================================================
# Streamlit page
# =========================================================

def main() -> None:
    st.set_page_config(page_title="Sector Indices", page_icon="📊", layout="wide")

    st.title("Sector Indices")
    st.caption(
        "Select an NSE index, fetch its constituent stocks and build "
        "candlestick charts for the top movers."
    )

    # -----------------------------------------------------
    # NSE session
    # -----------------------------------------------------

    if "nse_session" not in st.session_state:
        with st.spinner("Connecting to NSE..."):
            try:
                st.session_state.nse_session = create_nse_session()
            except Exception as exc:
                st.error(f"Could not connect to NSE: {exc}")

    session = st.session_state.get("nse_session")

    if session is None:
        return

    # -----------------------------------------------------
    # Load available index names
    # -----------------------------------------------------

    if "index_names" not in st.session_state:
        if st.button("📥 Load Available Indices", type="primary"):
            with st.spinner("Fetching available NSE indices..."):
                try:
                    st.session_state.index_names = fetch_index_names(session)
                except Exception as exc:
                    st.error(f"Could not fetch indices: {exc}")

    if not st.session_state.get("index_names"):
        st.info("Click **Load Available Indices** to fetch the list of NSE indexes.")
        return

    index_names = st.session_state["index_names"]

    col_idx, col_n, col_period = st.columns([3, 1, 1])

    with col_idx:
        index_name = st.selectbox("Select Index / Sector", index_names, key="sector_index")

    with col_n:
        top_n = st.selectbox("Top moving stocks", [5, 10, 15, 20, 25], index=0)

    with col_period:
        chart_period = st.selectbox("Chart Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)

    if st.button("🚀 Fetch Top Moving Stocks & Generate Charts", type="primary"):
        with st.spinner(f"Fetching constituents for {index_name}..."):
            try:
                constituents_df = fetch_index_constituents(session, index_name)
            except Exception as exc:
                st.error(f"Could not fetch constituents for {index_name}: {exc}")
                return

        if constituents_df.empty:
            st.warning(f"No constituent data returned for {index_name}.")
            return

        pchange_col = next(
            (c for c in ("pChange", "percentChange") if c in constituents_df.columns),
            None,
        )

        if pchange_col is not None:
            constituents_df = constituents_df[
                pd.to_numeric(constituents_df[pchange_col], errors="coerce").notna()
            ].copy()
            constituents_df = constituents_df.sort_values(
                pchange_col, ascending=False
            ).reset_index(drop=True)

        top_stocks = constituents_df.head(top_n).copy()

        display_cols = [
            "symbol",
            "previousClose",
            "lastPrice",
            "open",
            "dayHigh",
            "dayLow",
            "change",
            "pChange",
            "percentChange",
        ]
        display_cols = [c for c in display_cols if c in top_stocks.columns]

        st.subheader(f"Top {len(top_stocks)} Moving Stocks — {index_name}")
        st.dataframe(top_stocks[display_cols], use_container_width=True, hide_index=True)

        symbols = top_stocks["symbol"].tolist()

        # -------------------------------------------------
        # Download history and save charts
        # -------------------------------------------------

        clear_charts(CHART_FOLDER)

        progress = st.progress(0, text="Downloading data & saving charts...")

        for position, symbol in enumerate(symbols, start=1):
            progress.progress(
                (position - 1) / len(symbols),
                text=f"[{position}/{len(symbols)}] {symbol}",
            )

            yf_symbol = f"{symbol}.NS"
            data = download_history(yf_symbol, chart_period)

            if data is not None and not data.empty:
                save_stock_chart(yf_symbol, data, CHART_FOLDER)

            time.sleep(REQUEST_DELAY_SECONDS)

        progress.empty()

        st.success(
            f"Saved {len(symbols)} candidate charts to `{CHART_FOLDER}`"
        )

        # -------------------------------------------------
        # Show charts with screener links
        # -------------------------------------------------

        st.subheader(f"📈 Top {len(symbols)} Movers — Charts & Screener")
        st.caption(f"📂 Charts saved in: `{CHART_FOLDER}`")

        lookup_col = pchange_col if pchange_col is not None else "symbol"

        for symbol in symbols:
            yf_symbol = f"{symbol}.NS"
            chart_path = CHART_FOLDER / f"{yf_symbol}.png"
            screener_url = stock_utils.screener_company_url(symbol)

            matched = top_stocks[top_stocks["symbol"] == symbol]

            if not matched.empty and lookup_col in matched.columns:
                change_value = matched.iloc[0][lookup_col]

                try:
                    change_value = float(change_value)
                    header = f"### {symbol} — {change_value:+.2f}%"
                except (TypeError, ValueError):
                    header = f"### {symbol} — Change: {change_value}%"
            else:
                header = f"### {symbol}"

            st.markdown(header)
            st.markdown(f"[🔗 Open on Screener.in]({screener_url})")

            if chart_path.exists():
                st.image(str(chart_path), use_container_width=True)
            else:
                st.warning("Chart not available for this stock.")

        st.markdown("---")
        st.caption("Data: NSE for index constituents | Yahoo Finance for price history | mplfinance for charts")


if __name__ == "__main__":
    main()