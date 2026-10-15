
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================================================
# Configuration
# =========================================================

BASE_URL = (
    "https://www.moneycontrol.com/markets/earnings/results-calendar/"
)
HOME_URL = "https://www.moneycontrol.com/"

START_DATE = date(2026, 10, 5)
WEEKS_TO_FETCH = 8
REQUEST_DELAY_SECONDS = 1.0

OUTPUT_DIR = Path("data")
OUTPUT_EXCEL = OUTPUT_DIR / "moneycontrol_earnings_calendar.xlsx"
OUTPUT_CSV = OUTPUT_DIR / "moneycontrol_earnings_calendar.csv"

TABLE_SELECTOR = "table[class*='ResultTableWeb_table']"

COLUMNS = [
    "Result Date",
    "Company Name",
    "Company URL",
    "Result Type",
    "Time",
    "LTP",
    "% Change",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": HOME_URL,
}


# =========================================================
# URL and session
# =========================================================

def build_url(result_date: date) -> str:
    """Build the classic earnings calendar URL for a date."""
    params = {
        "classic": "true",
        "activeDate": result_date.isoformat(),
    }
    return f"{BASE_URL}?{urlencode(params)}"


def create_session() -> requests.Session:
    """Create a reusable HTTP session."""
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(HOME_URL, timeout=30)
        print(f"Homepage status: HTTP {response.status_code}")
    except requests.RequestException as error:
        print(f"Could not initialize homepage session: {error}")

    return session


# =========================================================
# HTML extraction
# =========================================================

def extract_table_rows(
    html: str,
    result_date: date,
) -> list[dict]:
    """Extract earnings rows from the HTML response."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(TABLE_SELECTOR)

    if table is None:
        print(
            f"No earnings table found for {result_date}. "
            "The table may be loaded dynamically."
        )
        return []

    results = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)

        # Expected columns:
        # Checkbox, Company, Result Type, Time, LTP, % Change, Expand
        if len(cells) < 6:
            continue

        company_link = cells[1].find("a", href=True)

        company_name = (
            company_link.get_text(" ", strip=True)
            if company_link
            else cells[1].get_text(" ", strip=True)
        )

        company_url = (
            company_link["href"]
            if company_link
            else None
        )

        if not company_name:
            continue

        results.append({
            "Result Date": result_date.isoformat(),
            "Company Name": company_name,
            "Company URL": company_url,
            "Result Type": cells[2].get_text(" ", strip=True),
            "Time": cells[3].get_text(" ", strip=True),
            "LTP": cells[4].get_text(" ", strip=True),
            "% Change": cells[5].get_text(" ", strip=True),
        })

    return results


# =========================================================
# Fetch one date
# =========================================================

def fetch_results_for_date(
    session: requests.Session,
    result_date: date,
) -> list[dict]:
    """Fetch and extract the earnings calendar for one date."""
    url = build_url(result_date)

    print(f"\nFetching {result_date}: {url}")

    try:
        response = session.get(url, timeout=30)

        print(
            f"HTTP status: {response.status_code}; "
            f"response size: {len(response.text)} characters"
        )

        if response.status_code == 403:
            print(
                "Access denied (403). This date could not be extracted. "
                "The server may restrict automated requests."
            )
            return []

        if response.status_code == 429:
            print(
                "Rate limited (429). Stop automated requests and "
                "retry later in accordance with the site's access rules."
            )
            return []

        response.raise_for_status()

        rows = extract_table_rows(response.text, result_date)
        print(f"Extracted {len(rows)} companies.")

        return rows

    except requests.RequestException as error:
        print(f"Request failed for {result_date}: {error}")
        return []


# =========================================================
# Fetch the full date range
# =========================================================

def fetch_eight_weeks() -> tuple[list[dict], list[str]]:
    """Fetch 56 calendar dates, beginning on START_DATE."""
    end_date = START_DATE + timedelta(
        days=(WEEKS_TO_FETCH * 7) - 1
    )

    all_results = []
    failed_dates = []

    session = create_session()

    try:
        current_date = START_DATE

        while current_date <= end_date:
            rows = fetch_results_for_date(session, current_date)

            if rows:
                all_results.extend(rows)
            else:
                failed_dates.append(current_date.isoformat())

            current_date += timedelta(days=1)

            if current_date <= end_date:
                time.sleep(REQUEST_DELAY_SECONDS)

    finally:
        session.close()

    print(f"\nRequested date range: {START_DATE} to {end_date}")
    print(f"Total extracted rows: {len(all_results)}")
    print(f"Dates with no extracted rows: {len(failed_dates)}")

    return all_results, failed_dates


# =========================================================
# Save Excel and CSV
# =========================================================

def save_results(
    results: list[dict],
    failed_dates: list[str],
) -> None:
    """Save extracted results and a failed-date report."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(results, columns=COLUMNS)

    if not df.empty:
        df = df.drop_duplicates(
            subset=[
                "Result Date",
                "Company Name",
                "Result Type",
            ]
        )

        df = df.sort_values(
            ["Result Date", "Company Name"]
        ).reset_index(drop=True)

    df.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    df.to_excel(
        OUTPUT_EXCEL,
        index=False,
    )

    failed_df = pd.DataFrame({
        "Date": failed_dates,
    })

    failed_report = OUTPUT_DIR / "moneycontrol_failed_dates.csv"
    failed_df.to_csv(
        failed_report,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n========== EXTRACTION SUMMARY ==========")
    print(f"Total records: {len(df)}")
    print(f"Excel file: {OUTPUT_EXCEL.resolve()}")
    print(f"CSV file: {OUTPUT_CSV.resolve()}")
    print(f"Failed-date report: {failed_report.resolve()}")

    if not df.empty:
        print("\nSample results:")
        print(df.head(10).to_string(index=False))
    else:
        print(
            "\nNo records were extracted. Check the HTTP status codes "
            "and whether the table exists in the returned HTML."
        )

    if failed_dates:
        print("\nDates requiring verification:")
        print(", ".join(failed_dates))


# =========================================================
# Main
# =========================================================

def main():
    results, failed_dates = fetch_eight_weeks()
    save_results(results, failed_dates)


if __name__ == "__main__":
    main()
