import yfinance as yf
import pandas as pd
import logging
import time
import requests
from bs4 import BeautifulSoup
import json



logger = logging.getLogger(__name__)

# ==========================================================
# SCREENER CONFIG
# ==========================================================

SCREENER_BASE_URL = "https://www.screener.in/company"

SCREENER_API_BASE_URL = "https://www.screener.in/api/company"

SCREENER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SCREENER_TIMEOUT = 20
SCREENER_MAX_RETRIES = 3
SCREENER_RETRY_BACKOFF = 1.5

# Company pages are much larger than this, while the peers table is a small
# HTML fragment that is checked with SCREENER_MIN_FRAGMENT_LENGTH instead
SCREENER_MIN_PAGE_LENGTH = 5000
SCREENER_MIN_FRAGMENT_LENGTH = 500

# Reused across calls so keep-alive connections are not rebuilt every rerun
_session = None


def clean_symbol(ticker: str) -> str:
    """Return the bare Screener symbol from a yfinance ticker.

    'TATATECH.NS' -> 'TATATECH'
    """
    return str(ticker).split(".")[0].strip().upper()


def screener_company_url(ticker: str, consolidated: bool = False) -> str:
    """Build the Screener company page URL for a ticker or symbol."""
    symbol = clean_symbol(ticker)
    suffix = "/consolidated" if consolidated else ""
    return f"{SCREENER_BASE_URL}/{symbol}{suffix}/"


def get_session() -> requests.Session:
    """Return the shared requests session configured for Screener."""
    global _session

    if _session is None:
        _session = requests.Session()
        _session.headers.update(SCREENER_HEADERS)

    return _session


def reset_session() -> None:
    """Drop the shared session, used when Screener starts rejecting requests."""
    global _session

    if _session is not None:
        try:
            _session.close()
        except Exception:
            pass

    _session = None


def _request_page(url: str, min_length: int = SCREENER_MIN_PAGE_LENGTH):
    """GET a Screener page with retries, returning the response or None.

    Screener intermittently answers 200 with a truncated body, so a response
    is only accepted when its body is at least min_length characters long.
    """
    last_status = None

    for attempt in range(1, SCREENER_MAX_RETRIES + 1):
        try:
            response = get_session().get(url, timeout=SCREENER_TIMEOUT)
        except requests.RequestException as e:
            logger.warning("Attempt %s/%s for %s failed: %s", attempt, SCREENER_MAX_RETRIES, url, e)
            reset_session()
            time.sleep(SCREENER_RETRY_BACKOFF * attempt)
            continue

        last_status = response.status_code

        if response.status_code != 200:
            logger.warning("Attempt %s/%s for %s returned %s", attempt, SCREENER_MAX_RETRIES, url, response.status_code)
            time.sleep(SCREENER_RETRY_BACKOFF * attempt)
            continue

        # a truncated body still returns 200, so sanity check the markup
        if len(response.text) < min_length:
            logger.warning("Attempt %s/%s for %s returned a truncated body", attempt, SCREENER_MAX_RETRIES, url)
            time.sleep(SCREENER_RETRY_BACKOFF * attempt)
            continue

        return response

    logger.warning("Giving up on %s (last status %s)", url, last_status)

    return None


def fetch_screener_page(ticker: str, consolidated: bool = False):
    """GET a Screener company page and return the BeautifulSoup object.

    Returns None when the page cannot be loaded.
    """
    url = screener_company_url(ticker, consolidated=consolidated)

    response = _request_page(url)

    if response is None:
        return None

    return BeautifulSoup(response.text, "lxml")


def get_financials_page(ticker: str, consolidated: bool = False):
    """Fetch the company page, falling back to the consolidated view.

    Screener hides the standalone sections for some companies, so a missing
    'quarters' section is retried against the consolidated page.
    """
    soup = fetch_screener_page(ticker, consolidated=consolidated)

    if soup is None:
        return None

    if soup.find("section", {"id": "quarters"}) is None and not consolidated:
        logger.info("No quarters section on standalone page, trying consolidated")
        fallback = fetch_screener_page(ticker, consolidated=True)

        if fallback is not None and fallback.find("section", {"id": "quarters"}) is not None:
            return fallback

    return soup


# ==========================================================
# PEER COMPARISON
# ==========================================================


def get_company_warehouse_id(soup) -> str | None:
    """Return Screener's warehouse id from a company page.

    The peers table is served from a separate API endpoint keyed by this id.
    """
    if soup is None:
        return None

    company_info = soup.find(id="company-info")

    if company_info is None:
        logger.warning("No company-info element on the page")
        return None

    warehouse_id = company_info.get("data-warehouse-id")

    return warehouse_id or None


def fetch_peers_page(warehouse_id: str | None):
    """GET the peers table fragment for a warehouse id.

    Returns None when the fragment cannot be loaded.
    """
    if not warehouse_id:
        return None

    url = f"{SCREENER_API_BASE_URL}/{warehouse_id}/peers/"

    response = _request_page(url, min_length=SCREENER_MIN_FRAGMENT_LENGTH)

    if response is None:
        return None

    return BeautifulSoup(response.text, "lxml")


def symbol_from_company_url(href) -> str | None:
    """Return the Screener symbol from a company link.

    '/company/LTTS/consolidated/' -> 'LTTS'
    '/company/TATATECH/'          -> 'TATATECH'
    """
    if not href:
        return None

    parts = [part for part in str(href).split("/") if part]

    if len(parts) < 2 or parts[0] != "company" or not parts[1]:
        return None

    return parts[1].upper()


def extract_peer_symbols(soup) -> list[str]:
    """Return the company symbols listed in a peers table.

    Accepts either a company page or the peers table fragment. Only links
    inside the table are read, so the benchmark links that sit in the same
    section are ignored. Returns an empty list when no table is present.
    """
    if soup is None:
        return []

    section = soup.find("section", {"id": "peers"})
    table = section.find("table") if section is not None else soup.find("table")

    if table is None:
        logger.warning("No peers table found")
        return []

    symbols = []

    for link in table.select('a[href^="/company/"]'):
        symbol = symbol_from_company_url(link.get("href"))

        if symbol is not None and symbol not in symbols:
            symbols.append(symbol)

    return symbols


def get_peer_symbols(ticker: str, soup=None) -> list[str]:
    """Return the peer symbols of a company as shown on Screener.

    The company page only holds a placeholder for the peers table, so the
    table is fetched from the API it points at. The company itself is part
    of its own peers table and is dropped from the result.
    """
    if soup is None:
        soup = fetch_screener_page(ticker)

    warehouse_id = get_company_warehouse_id(soup)
    peers_page = fetch_peers_page(warehouse_id)
    symbols = extract_peer_symbols(peers_page)

    if not symbols:
        logger.warning("No peer symbols found for %s", ticker)
        return []

    own_symbol = clean_symbol(ticker)

    return [symbol for symbol in symbols if symbol != own_symbol]


def build_peer_financial_summaries(symbols: list[str]) -> dict:
    """Build the financial summary JSON for every peer symbol.

    A peer that cannot be fetched is stored under an 'error' key so one bad
    company does not drop the rest of the table.
    """
    summaries = {}

    for symbol in symbols:
        try:
            logger.info("Building peer financial summary for %s", symbol)

            df_year, df_quarter = get_financials(symbol)
            summaries[symbol] = build_financial_summary(df_year, df_quarter)
        except Exception as e:
            logger.warning("Could not build peer summary for %s: %s", symbol, e)
            summaries[symbol] = {"error": str(e)}

    return summaries


def parse_screener_table(soup, section_id: str, label: str):
    """Parse one Screener results table into a DataFrame.

    Returns an empty DataFrame when the section, table or rows are missing.
    """
    empty = pd.DataFrame()

    if soup is None:
        return empty

    section = soup.find("section", {"id": section_id})

    if section is None:
        logger.warning("Section %r not found", section_id)
        return empty

    table = section.find("table")

    if table is None:
        logger.warning("No table inside section %r", section_id)
        return empty

    thead = table.find("thead")

    if thead is None:
        logger.warning("No header row in section %r", section_id)
        return empty

    columns = []

    for th in thead.find_all("th"):
        text = th.get_text(strip=True)
        columns.append(text if text else label)

    tbody = table.find("tbody")

    if tbody is None:
        logger.warning("No body rows in section %r", section_id)
        return pd.DataFrame(columns=columns)

    rows_data = []

    for row in tbody.find_all("tr"):
        row_data = []

        for col in row.find_all("td"):
            text = col.get_text(" ", strip=True).replace("+", "").strip()
            row_data.append(text)

        # the label-only rows (Raw PDF, etc.) carry a single cell
        if len(row_data) > 1:
            rows_data.append(row_data)

    if not rows_data:
        # headers but no rows just means the company has not reported that
        # period yet, which is expected for recent listings
        logger.info("Section %r has no data rows", section_id)
        return pd.DataFrame(columns=columns)

    width = len(columns)

    # guard against ragged rows so DataFrame construction cannot fail
    rows_data = [(r + [""] * width)[:width] for r in rows_data]

    return pd.DataFrame(rows_data, columns=columns)


# def fetch_ticker(ticker: str):
#     """Return a yfinance Ticker object for the given ticker."""
#     return yf.Ticker(ticker)


def get_company_info(ticker: str) -> dict:
    """Extract commonly used company info from a yf.Ticker object.

    Returns a dict with keys used by the Streamlit page.
    """
    info = {}
    try:
        stock = yf.Ticker(ticker)
        meta = stock.info or {}
    except Exception:
        meta = {}

    info["company_name"] = meta.get("longName", "N/A")
    info["sector"] = meta.get("sector", "N/A")
    info["industry"] = meta.get("industry", "N/A")
    info["website"] = meta.get("website", "N/A")
    info["country"] = meta.get("country", "N/A")
    info["employees"] = meta.get("fullTimeEmployees", "N/A")
    info["description"] = meta.get("longBusinessSummary", "N/A")
    info["current_price"] = meta.get("currentPrice", "N/A")
    info["fifty_two_high"] = meta.get("fiftyTwoWeekHigh", "N/A")
    info["fifty_two_low"] = meta.get("fiftyTwoWeekLow", "N/A")

    return info


def get_financial_df(stock):
    """Return a cleaned dataframe with yearly revenue, net profit and margin.

    Returns None if financials are not available or cannot be parsed.
    """
    try:
        financials = stock.financials
    except Exception as e:
        logger.exception("Error fetching financials: %s", e)
        return None

    if financials is None or financials.empty:
        return None

    # Try to safely extract revenue and net income rows
    try:
        revenue = financials.loc["Total Revenue"]
        net_income = financials.loc["Net Income"]
    except Exception:
        # If expected rows are missing, return None
        return None

    profit_margin = (net_income / revenue) * 100

    df = pd.DataFrame({
        "Year": revenue.index.strftime("%Y"),
        "Gross Revenue": revenue.values,
        "Net Profit": net_income.values,
        "Profit Margin %": profit_margin.values,
    })

    df = df.dropna()

    if df.empty:
        return None

    return df


def calculate_cagr(df):
    """Calculate revenue and profit CAGR from the financial dataframe.

    Returns (revenue_cagr, profit_cagr) in percent or (None, None)
    when not enough data is available.
    """
    if df is None or len(df) < 2:
        return None, None

    try:
        start_revenue = df.iloc[-1]["Sales"]
        end_revenue = df.iloc[0]["Sales"]
        start_profit = df.iloc[-1]["Net Profit"]
        end_profit = df.iloc[0]["Net Profit"]
        years = len(df) - 1

        revenue_cagr = (((end_revenue / start_revenue) ** (1 / years)) - 1) * 100
        profit_cagr = (((end_profit / start_profit) ** (1 / years)) - 1) * 100
    except Exception:
        return None, None

    return revenue_cagr, profit_cagr


def to_number(value):
    """Parse a Screener cell value into a float.

    Handles thousands separators ('1,217'), currency symbols, percent signs
    ('25%'), negative values ('-2,145'), accounting negatives ('(2,145)'),
    em/en dashes used as blanks and returns NaN for anything unparseable.
    """
    if value is None:
        return float("nan")

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    # blank placeholders
    if text in ("", "-", "--", "\u2013", "\u2014"):
        return float("nan")

    # accounting style negatives
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    # unicode minus / en dash used as a negative sign
    text = text.replace("\u2212", "-").replace("\u2013", "-")

    for token in (",", "%", "\u20b9", "Rs.", "Rs", "rs.", "rs", " "):
        text = text.replace(token, "")

    # a trailing '-' is a negative sign, not a separator
    while text.startswith("-"):
        negative = not negative
        text = text[1:]

    if text == "":
        return float("nan")

    try:
        number = float(text)
    except ValueError:
        return float("nan")

    return -abs(number) if negative else number


def get_period_columns(df_year):
    """Return the period column labels ('Mar 2019', ...) from a results df."""
    if df_year is None or df_year.empty:
        return []

    columns = list(df_year.columns)

    if columns and str(columns[0]).strip() in METRIC_INDEX_LABELS:
        columns = columns[1:]

    return columns


def get_metric_series(df_year, metric):
    """Return a numeric Series for a metric row of the yearly results df.

    The index holds the period labels, so the series stays aligned with
    get_period_columns(df_year).
    """
    df = get_metric_index(df_year)

    if df.empty:
        return pd.Series(dtype="float64")

    if metric not in df.index:
        logger.warning("Metric %r not found in yearly results", metric)
        return pd.Series(index=df.columns, dtype="float64")

    return df.loc[metric].map(to_number)


# Row names Screener uses for the top line, in priority order. Companies
# report this as 'Sales' or 'Revenue' depending on their sector.
REVENUE_METRICS = ("Sales", "Revenue", "Total Revenue", "Net Sales", "Gross Revenue")

# First column labels that hold the metric names rather than a period
METRIC_INDEX_LABELS = ("Years", "Particulars", "Quarter")


def get_metric_index(df_year):
    """Return the results df re-indexed by trimmed metric name.

    Handles both the yearly table ('Years') and the quarterly table
    ('Particulars').
    """
    if df_year is None or df_year.empty:
        return pd.DataFrame()

    df = df_year.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if df.columns[0] in METRIC_INDEX_LABELS:
        df = df.set_index(df.columns[0])

    df.index = [str(i).strip() for i in df.index]

    return df


def get_revenue_metric_name(df_year):
    """Return the actual row name Screener used for the top line.

    Charts need the real label, otherwise a company reporting 'Revenue'
    raises a KeyError when the chart asks for 'Sales'.
    """
    index = get_metric_index(df_year)

    for metric in REVENUE_METRICS:
        if metric in index.index:
            return metric

    return None


def get_revenue_series(df_year):
    """Return the top line as a numeric Series, whichever row name is used.

    Falls back to the first available metric from REVENUE_METRICS.
    """
    if df_year is None or df_year.empty:
        return pd.Series(dtype="float64")

    df = get_metric_index(df_year)

    metric = next((m for m in REVENUE_METRICS if m in df.index), None)

    if metric is None:
        logger.warning(
            "No revenue row found, looked for %s", ", ".join(REVENUE_METRICS)
        )
        return pd.Series(dtype="float64")

    return df.loc[metric].map(to_number)


def calculate_growth_and_margins(df_year):
    """Build a period-wise table of revenue growth and net profit margin.

    Columns returned: Revenue, Net Profit, Revenue Growth, Revenue Growth %,
    Net Profit Margin %. The first period has no growth value (NaN) since
    there is no prior period to compare against.

    Returns an empty DataFrame when revenue or net profit are unavailable.
    """
    sales = get_revenue_series(df_year)
    profit = get_metric_series(df_year, "Net Profit")
    opm = get_metric_series(df_year, "OPM %")

    if sales.empty or sales.dropna().empty:
        return pd.DataFrame()

    df = pd.DataFrame({
        "Revenue": sales,
        "Net Profit": profit,
        "Operating Profit Margin %" : opm
    })

    df.index.name = "Period"

    # A zero (or missing) revenue period would make pct_change return inf,
    # which then poisons any average. Treat zeros as missing first.
    safe_sales = df["Revenue"].replace(0, float("nan"))

    df["Revenue Growth"] = df["Revenue"].diff().round(2)
    df["Revenue Growth %"] = (safe_sales.pct_change() * 100).round(2)
    df["Revenue Growth %"] = df["Revenue Growth %"].replace(
        [float("inf"), float("-inf")], float("nan")
    )

    df["Net Profit Margin %"] = (df["Net Profit"] / safe_sales * 100).round(2)

    return df.reset_index()


def classify_trend(values, up_threshold: float = 2.0, down_threshold: float = -2.0) -> str:
    """Classify a series as Upward, Consolidated or Downward.

    Uses the mean period-over-period change relative to the average magnitude
    of the series, so it stays meaningful for values in any unit.
    """
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()

    if len(series) < 2:
        return "Consolidated"

    scale = series.abs().mean()

    if not scale or pd.isna(scale) or scale == 0:
        return "Consolidated"

    change_pct = (series.diff().dropna().mean() / scale) * 100

    if pd.isna(change_pct):
        return "Consolidated"

    if change_pct >= up_threshold:
        return "Upward"

    if change_pct <= down_threshold:
        return "Downward"

    return "Consolidated"


def _round_or_none(value, digits: int = 2):
    """Round a value for JSON output, mapping NaN/NaT to None."""
    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        return [_round_or_none(v, digits) for v in value]

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if pd.isna(number):
        return None

    return round(number, digits)


def _tail(series, n: int):
    """Return the last n values of a series, oldest first, as a plain list."""
    if series is None:
        return []

    cleaned = pd.to_numeric(pd.Series(series), errors="coerce").dropna()

    return cleaned.tail(n).tolist()


def _tail_by_period(df, column: str, n: int) -> dict:
    """Return the last n values of a column keyed by their period label.

    Keeps the order they appear in the source table, so the caller can tell
    which year or quarter each value belongs to.

    {'Mar 2024': 29.36, 'Mar 2025': 10.69, 'Mar 2026': 3.37}
    """
    if df is None or df.empty or column not in df.columns:
        return {}

    if "Period" not in df.columns:
        return {}

    frame = df[["Period", column]].copy()
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=[column]).tail(n)

    return {
        str(period): round(float(value), 2)
        for period, value in zip(frame["Period"], frame[column])
    }


def _mean_or_none(series):
    """Mean of a series, or None when there is nothing to average."""
    if series is None:
        return None

    cleaned = pd.to_numeric(pd.Series(series), errors="coerce").replace(
        [float("inf"), float("-inf")], float("nan")
    ).dropna()

    if cleaned.empty:
        return None

    return cleaned.mean()


def build_financial_summary(df_year, df_quarter) -> dict:
    """Build the JSON summary of yearly and quarterly performance.

    Missing values are reported as None so the payload stays valid JSON.
    """
    summary = {
        "Revenue_Trend": None,
        "Net_Profit_Trend": None,
        "Avg_Revenue_Growth_Per": None,
        "Last_3_years_Growth_Per": {},
        "Avg_Operating_Margin": None,
        "Avg_Net_Profit_Margin": None,
        "Last_3_Years_Operating_Margin": {},
        "Last_3_Years_Net_Profit_Margin": {},
        "Last_5_Quarter_Revenue_Avg": None,
        "Last_5_Quarter_Net_Profit_Avg": None,
    }

    df_growth = calculate_growth_and_margins(df_year)

    if not df_growth.empty:
        growth = df_growth["Revenue Growth %"]
        operating_margin = (
            df_growth["Operating Profit Margin %"]
            if "Operating Profit Margin %" in df_growth.columns
            else pd.Series(dtype="float64")
        )

        summary["Revenue_Trend"] = classify_trend(df_growth["Revenue"])
        summary["Net_Profit_Trend"] = classify_trend(df_growth["Net Profit"])
        summary["Avg_Revenue_Growth_Per"] = _round_or_none(_mean_or_none(growth))
        summary["Last_3_years_Growth_Per"] = _tail_by_period(df_growth, "Revenue Growth %", 3)
        summary["Avg_Operating_Margin"] = _round_or_none(_mean_or_none(operating_margin))
        summary["Avg_Net_Profit_Margin"] = _round_or_none(
            _mean_or_none(df_growth["Net Profit Margin %"])
        )
        summary["Last_3_Years_Operating_Margin"] = _tail_by_period(
            df_growth, "Operating Profit Margin %", 3
        )
        summary["Last_3_Years_Net_Profit_Margin"] = _tail_by_period(
            df_growth, "Net Profit Margin %", 3
        )

    quarterly_revenue = get_revenue_series(df_quarter)
    quarterly_profit = get_metric_series(df_quarter, "Net Profit")

    summary["Last_5_Quarter_Revenue_Avg"] = _round_or_none(_mean_or_none(_tail(quarterly_revenue, 5)))
    summary["Last_5_Quarter_Net_Profit_Avg"] = _round_or_none(_mean_or_none(_tail(quarterly_profit, 5)))

    return summary


def get_history(ticker: str, period: str = "1y"):
    """Return historical price data for the given period."""
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period=period)
    except Exception as e:
        logger.exception("Error fetching history: %s", e)
        return None
    

def get_quarterly_results(stock, soup=None):
    """Return the quarterly results table as a DataFrame.

    Pass soup to reuse an already fetched page instead of requesting again.
    """
    if soup is None:
        soup = get_financials_page(stock)

    return parse_screener_table(soup, "quarters", "Particulars")


def get_yearly_results(stock, soup=None):
    """Return the yearly profit & loss table as a DataFrame.

    Pass soup to reuse an already fetched page instead of requesting again.
    """
    if soup is None:
        soup = fetch_screener_page(stock)

    df = parse_screener_table(soup, "profit-loss", "Years")

    if "TTM" in df.columns:
        df = df.drop(columns=["TTM"])

    return df


def get_financials(stock):
    """Fetch the company page once and return (yearly, quarterly) DataFrames.

    Both tables live on the same page, so this halves the number of requests
    and guarantees the two tables always come from the same snapshot.
    """
    soup = get_financials_page(stock)

    df_year = parse_screener_table(soup, "profit-loss", "Years")

    if "TTM" in df_year.columns:
        df_year = df_year.drop(columns=["TTM"])

    df_quarter = parse_screener_table(soup, "quarters", "Particulars")
    return df_year, df_quarter


# ==========================================================
# SCREENER COMPANY INFO
# ==========================================================


def _remove_citations(node) -> None:
    """Drop the [1] citation links Screener appends to sourced text."""
    if node is None:
        return

    for sup in node.find_all("sup"):
        if sup.find("a") is not None:
            sup.decompose()


def _find_section_content(soup, title: str):
    """Return the content div that follows a titled block on the page.

    Screener renders About and Key Points as a 'div.title' heading followed
    by its content in the next sibling div. Returns None when the heading
    is missing.
    """
    if soup is None:
        return None

    heading = next(
        (
            div
            for div in soup.find_all("div", class_="title")
            if div.get_text(" ", strip=True).lower() == title.lower()
        ),
        None,
    )

    if heading is None:
        return None

    return heading.find_next_sibling("div")


def extract_screener_company_info(symbol: str, soup=None) -> dict | None:
    """Return the About text and Key Points of a company from Screener.

    Pass soup to reuse an already fetched page instead of requesting again.

    Returns None when the page cannot be loaded. Sections that are missing
    come back as empty values so the result can still be rendered.
    """
    symbol = clean_symbol(symbol)

    if soup is None:
        soup = fetch_screener_page(symbol)

    if soup is None:
        logger.warning("Could not load the Screener page for %s", symbol)
        return None

    heading = soup.find("h1")
    company_name = heading.get_text(" ", strip=True) if heading else symbol

    # ------------------------------------------------------
    # About
    # ------------------------------------------------------

    about = ""
    about_block = _find_section_content(soup, "About")

    if about_block is None:
        logger.warning("No About section on the page for %s", symbol)
    else:
        _remove_citations(about_block)
        about = about_block.get_text(" ", strip=True)

    # ------------------------------------------------------
    # Key Points
    # ------------------------------------------------------

    key_points = []
    key_points_block = _find_section_content(soup, "Key Points")

    if key_points_block is None:
        logger.warning("No Key Points section on the page for %s", symbol)
    else:
        _remove_citations(key_points_block)

        for paragraph in key_points_block.find_all("p"):
            strong = paragraph.find("strong")
            point_title = strong.get_text(" ", strip=True) if strong else ""
            point_text = paragraph.get_text(" ", strip=True)

            # the title repeats at the start of the paragraph, so only the
            # remainder is kept as the description
            if point_title and point_text.startswith(point_title):
                description = point_text[len(point_title):].strip()
            else:
                description = point_text

            key_points.append({
                "title": point_title,
                "description": description,
            })

    # ------------------------------------------------------
    # Final JSON structure
    # ------------------------------------------------------

    return {
        "symbol": symbol,
        "company_name": company_name,
        "about": about,
        "key_points": key_points,
    }


# # ==========================================================
# # USAGE
# # ==========================================================

# url = "https://www.screener.in/company/H"

# df = get_quarterly_results(url)

# print(df)