

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

import logging
import math
import os

from datetime import datetime

import pages.utils.stock_utils as stock_utils

# ==========================================================
# LOGGER SETUP
# ==========================================================

if not os.path.exists("logs"):
    os.makedirs("logs")

log_filename = (
    f"logs/stock_dashboard_"
    f"{datetime.now().strftime('%Y%m%d')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info("Application Started")

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

# ==========================================================
# TITLE
# ==========================================================

st.title("📈 Stock Analysis Dashboard")

# ==========================================================
# USER INPUT
# ==========================================================

def main():

    # ==========================================================
    # INPUT
    # ==========================================================

    ticker_input = st.text_input(
        "Enter NSE Stock Ticker",
        value="TATATECH.NS"
    )

    logger.info(f"User entered ticker: {ticker_input}")

    if not ticker_input:
        return

    # ==========================================================
    # STEP 1: DATA FETCHING / DATA PREPARATION
    # ==========================================================

    try:
        logger.info(f"Fetching stock data for: {ticker_input}")

        # ------------------------------------------------------
        # Company information
        # ------------------------------------------------------

        info = stock_utils.get_company_info(ticker_input)

        # ------------------------------------------------------
        # Screener information
        # ------------------------------------------------------

        screener_symbol = stock_utils.clean_symbol(ticker_input)

        url = stock_utils.screener_company_url(
            screener_symbol
        )

        # ------------------------------------------------------
        # Screener company information
        # ------------------------------------------------------

        screener_info = (
            stock_utils.extract_screener_company_info(
                screener_symbol
            )
        )

        # ------------------------------------------------------
        # Financial data
        # ------------------------------------------------------

        df_year, df_quarter = stock_utils.get_financials(
            screener_symbol
        )

        # ------------------------------------------------------
        # Financial calculations
        # ------------------------------------------------------

        df_growth = stock_utils.calculate_growth_and_margins(
            df_year
        )

        revenue_metric = stock_utils.get_revenue_metric_name(
            df_year
        )

        quarterly_revenue_metric = (
            stock_utils.get_revenue_metric_name(df_quarter)
        )

        # ------------------------------------------------------
        # Prepare yearly summary
        # ------------------------------------------------------

        df_summary = pd.DataFrame()

        if not df_year.empty:
            df_summary = df_year.set_index("Years").T
            df_summary.index.name = "Metrics"

        # ------------------------------------------------------
        # Prepare quarterly summary
        # ------------------------------------------------------

        df_quarter_summary = pd.DataFrame()

        if not df_quarter.empty:
            df_quarter_summary = df_quarter.set_index(
                "Particulars"
            ).T

            df_quarter_summary.index.name = "Year"

        # ------------------------------------------------------
        # Peer comparison
        # ------------------------------------------------------

        logger.info(f"Fetching peers for: {screener_symbol}")

        with st.spinner("Fetching peer companies..."):

            peer_symbols = stock_utils.get_peer_symbols(
                screener_symbol
            )

            peer_summaries = (
                stock_utils.build_peer_financial_summaries(
                    peer_symbols
                )
            )

        # ------------------------------------------------------
        # Financial summary JSON
        # ------------------------------------------------------

        financial_summary = stock_utils.build_financial_summary(
            df_year,
            df_quarter
        )

        # ------------------------------------------------------
        # Logging
        # ------------------------------------------------------

        logger.info(f"Yearly dataframe:\n{df_year}")

        logger.info(
            "##############################################################"
        )

        logger.info(
            f"Quarterly dataframe:\n{df_quarter}"
        )

        logger.info(f"Growth dataframe:\n{df_growth}")

        logger.info(f"Peer symbols: {peer_symbols}")

        logger.info(
            f"Company info loaded: {screener_info is not None}"
        )

        # ------------------------------------------------------
        # Data availability warnings
        # ------------------------------------------------------

        if df_year.empty:
            logger.warning(
                "Yearly financial data unavailable (rows=%s)",
                len(df_year)
            )

        if df_quarter.empty:
            logger.warning(
                "Quarterly financial data unavailable (rows=%s)",
                len(df_quarter)
            )

    except Exception as e:

        logger.exception(
            f"Error while fetching data for {ticker_input}"
        )

        st.error(
            f"Error fetching stock data: {e}"
        )

        # Stop execution.
        # UI should not try to use incomplete data.
        return

    # ==========================================================
    # STEP 2: UI / PRESENTATION
    # ==========================================================

    try:

        # ======================================================
        # COMPANY HEADER
        # ======================================================

        company_name = info.get(
            "company_name",
            "Unknown Company"
        )

        st.header(f"🏢 {company_name}")

        # ======================================================
        # BASIC METRICS
        # ======================================================

        col1, col2, col3 = st.columns(3)

        # Uncomment if required

        # col1.metric(
        #     "Current Price",
        #     info.get("current_price")
        # )

        # col2.metric(
        #     "52W High",
        #     info.get("fifty_two_high")
        # )

        # col3.metric(
        #     "52W Low",
        #     info.get("fifty_two_low")
        # )

        # ======================================================
        # SCREENER LINK
        # ======================================================

        st.markdown("### 🔗 Screener Link")

        st.write(url)

        # ======================================================
        # DATA AVAILABILITY
        # ======================================================

        if df_year.empty:
            st.error(
                "Yearly financial data not available."
            )

        if df_quarter.empty:
            st.warning(
                "Quarterly financial data not available "
                "for this company."
            )

        # ======================================================
        # YEARLY SECTION
        # ======================================================

        if not df_year.empty:

            st.subheader(
                "📊 Financial Trend Analysis"
            )

            st.markdown(
                "### Year-Wise Financial Trend"
            )

            # --------------------------------------------------
            # Revenue availability
            # --------------------------------------------------

            if revenue_metric is None:

                st.warning(
                    "Revenue row not reported for this company."
                )

            else:

                # --------------------------------------------------
                # Chart options
                # --------------------------------------------------

                chart_options = [
                    "Gross Revenue",
                    "Net Profit"
                ]

                if not df_growth.empty:
                    chart_options.append(
                        "Revenue Growth %"
                    )

                chart_option = st.selectbox(
                    "Select Chart",
                    chart_options
                )

                fig = None

                # --------------------------------------------------
                # Revenue chart
                # --------------------------------------------------

                if chart_option == "Gross Revenue":

                    fig = px.line(
                        df_summary,
                        x=df_summary.index,
                        y=revenue_metric,
                        markers=True,
                        title="Gross Revenue Trend",
                        color_discrete_sequence=["yellow"],
                        text=revenue_metric
                    )

                # --------------------------------------------------
                # Net Profit chart
                # --------------------------------------------------

                elif chart_option == "Net Profit":

                    fig = px.line(
                        df_summary,
                        x=df_summary.index,
                        y="Net Profit",
                        markers=True,
                        title="Net Profit Trend",
                        color_discrete_sequence=["yellow"],
                        text="Net Profit"
                    )

                # --------------------------------------------------
                # Revenue Growth chart
                # --------------------------------------------------

                elif chart_option == "Revenue Growth %":

                    growth_df = df_growth.dropna(
                        subset=["Revenue Growth %"]
                    )

                    if growth_df.empty:

                        st.info(
                            "Not enough periods to calculate growth."
                        )

                    else:

                        fig = px.bar(
                            growth_df,
                            x="Period",
                            y="Revenue Growth %",
                            title="Revenue Growth %",
                            color_discrete_sequence=["yellow"],
                            text="Revenue Growth %"
                        )

                        avg_growth = (
                            growth_df["Revenue Growth %"]
                            .mean()
                        )

                        if pd.notna(avg_growth):

                            fig.add_hline(
                                y=avg_growth,
                                line_dash="dash",
                                line_color="red",
                                annotation_text=(
                                    f"Avg {avg_growth:.2f}%"
                                ),
                                annotation_position="top left",
                                annotation_font_color="red"
                            )

                # --------------------------------------------------
                # Display chart
                # --------------------------------------------------

                if fig is not None:

                    fig.update_layout(
                        height=600,
                        xaxis_title="Year",
                        yaxis_title=chart_option
                    )

                    st.plotly_chart(
                        fig,
                        width="stretch"
                    )

            # ==================================================
            # PROFIT MARGINS
            # ==================================================

            if not df_growth.empty:

                st.subheader(
                    "Operating Profit & Net Profit Margin %"
                )

                # --------------------------------------------------
                # Find available margin columns
                # --------------------------------------------------

                margin_columns = [
                    column
                    for column in (
                        "Operating Profit Margin %",
                        "Net Profit Margin %"
                    )
                    if (
                        column in df_growth.columns
                        and df_growth[column].notna().any()
                    )
                ]

                # --------------------------------------------------
                # Prepare chart dataframe
                # --------------------------------------------------

                chart_df = (
                    df_growth.dropna(
                        subset=margin_columns,
                        how="all"
                    )
                    if margin_columns
                    else pd.DataFrame()
                )

                # --------------------------------------------------
                # Margin chart
                # --------------------------------------------------

                if (
                    margin_columns
                    and not chart_df.empty
                ):

                    growth_fig = px.bar(
                        chart_df,
                        x="Period",
                        y=margin_columns,
                        barmode="group",
                        title=(
                            "Operating Profit & "
                            "Net Profit Margin %"
                        ),
                        color_discrete_sequence=[
                            "yellow",
                            "green"
                        ],
                        labels={
                            "value": "Percent (%)",
                            "variable": "Metric",
                            "Period": "Year"
                        }
                    )

                    growth_fig.update_traces(
                        texttemplate="%{y:.2f}%",
                        textposition="outside",
                        textfont=dict(size=11),
                        marker_line=dict(
                            width=0.5,
                            color="black"
                        )
                    )

                    growth_fig.update_layout(
                        height=600,
                        xaxis_title="Year",
                        yaxis_title="Percent (%)",
                        legend_title_text="Metric",
                        bargap=0.15,
                        bargroupgap=0.05
                    )

                    st.plotly_chart(
                        growth_fig,
                        width="stretch"
                    )

                elif not margin_columns:

                    st.info(
                        "Operating profit margin not "
                        "reported for this company."
                    )

        # ======================================================
        # QUARTERLY SECTION
        # ======================================================

        if not df_quarter.empty:

            st.subheader(
                "Quarter-Wise Financial Trend"
            )

            # --------------------------------------------------
            # Revenue availability
            # --------------------------------------------------

            if quarterly_revenue_metric is None:

                st.warning(
                    "Revenue row not reported for this company."
                )

            else:

                chart_options_quarter = [
                    "Gross Revenue",
                    "Net Profit"
                ]

                chart_option_quarter = st.selectbox(
                    "Select Chart",
                    chart_options_quarter,
                    key="Quarter_Chart"
                )

                fig_quarter = None

                # --------------------------------------------------
                # Revenue
                # --------------------------------------------------

                if chart_option_quarter == "Gross Revenue":

                    fig_quarter = px.line(
                        df_quarter_summary,
                        x=df_quarter_summary.index,
                        y=quarterly_revenue_metric,
                        markers=True,
                        title="Gross Revenue Trend",
                        color_discrete_sequence=["yellow"],
                        text=quarterly_revenue_metric
                    )

                # --------------------------------------------------
                # Net Profit
                # --------------------------------------------------

                elif chart_option_quarter == "Net Profit":

                    fig_quarter = px.line(
                        df_quarter_summary,
                        x=df_quarter_summary.index,
                        y="Net Profit",
                        markers=True,
                        title="Net Profit Trend",
                        color_discrete_sequence=["yellow"],
                        text="Net Profit"
                    )

                # --------------------------------------------------
                # Display chart
                # --------------------------------------------------

                if fig_quarter is not None:

                    fig_quarter.update_traces(
                        mode="lines+markers+text",
                        textposition="top center",
                        textfont=dict(size=11)
                    )

                    fig_quarter.update_layout(
                        height=600,
                        xaxis_title="Quarter",
                        yaxis_title=chart_option_quarter
                    )

                    st.plotly_chart(
                        fig_quarter,
                        width="stretch"
                    )

        # ======================================================
        # PEER COMPARISON
        # ======================================================

        st.subheader("Peer Comparison")

        if peer_summaries:

            peer_df = (
                pd.DataFrame(peer_summaries)
                .T.reset_index(names="Symbol")
            )

            peer_columns = [
                "Symbol",
                "Revenue_Trend",
                "Net_Profit_Trend",
                "Avg_Revenue_Growth_Per",
                "Avg_Operating_Margin",
                "Avg_Net_Profit_Margin",
                "error"
            ]

            peer_columns = [
                column
                for column in peer_columns
                if column in peer_df.columns
            ]

            st.dataframe(
                data=peer_df[peer_columns],
                hide_index=True
            )

            with st.expander(
                "Peer Financial Summary JSON",
                expanded=False
            ):

                st.json(
                    peer_summaries,
                    expanded=False
                )

        # ======================================================
        # PEER VS COMPANY COMPARISON
        # ======================================================

        def _fmt_pct(value):
            """Format a percentage value for display."""
            if value is None:
                return "N/A"
            try:
                value = float(value)
            except (TypeError, ValueError):
                return "N/A"
            if pd.isna(value) or not math.isfinite(value):
                return "N/A"
            return f"{value:.2f}%"

        def _peer_avg(peer_data, key):
            """Average of a metric across peers, excluding failed lookups."""
            values = []
            for summary in peer_data.values():
                if not isinstance(summary, dict) or summary.get("error"):
                    continue
                value = summary.get(key)
                if value is None:
                    continue
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(value):
                    continue
                values.append(value)
            if not values:
                return None
            return sum(values) / len(values)

        def _peer_avg_last3(peer_data, key):
            """Average the last-3-year values stored per peer.

            Keys like 'Last_3_years_Growth_Per' hold a period -> value dict,
            so every peer's values are pooled before averaging.
            """
            values = []
            for summary in peer_data.values():
                if not isinstance(summary, dict) or summary.get("error"):
                    continue
                series = summary.get(key)
                if not isinstance(series, dict):
                    continue
                for value in series.values():
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        continue
                    if pd.isna(value) or not math.isfinite(value):
                        continue
                    values.append(value)
            if not values:
                return None
            return sum(values) / len(values)

        def _delta(company_value, peer_value):
            """Difference (percentage points) between company and peer average."""
            if company_value is None or peer_value is None:
                return "N/A"
            try:
                diff = float(company_value) - float(peer_value)
            except (TypeError, ValueError):
                return "N/A"
            if pd.isna(diff) or not math.isfinite(diff):
                return "N/A"
            return f"{diff:+.2f} pp"

        # Company values (last 3 years)
        company_rev_growth = None
        if not df_growth.empty and "Revenue Growth %" in df_growth.columns:
            recent = df_growth["Revenue Growth %"].dropna().tail(3)
            if not recent.empty:
                company_rev_growth = float(recent.mean())

        company_opm = None
        if not df_growth.empty and "Operating Profit Margin %" in df_growth.columns:
            recent = df_growth["Operating Profit Margin %"].dropna().tail(3)
            if not recent.empty:
                company_opm = float(recent.mean())

        company_npm = None
        if not df_growth.empty and "Net Profit Margin %" in df_growth.columns:
            recent = df_growth["Net Profit Margin %"].dropna().tail(3)
            if not recent.empty:
                company_npm = float(recent.mean())

        # 3 year net profit growth for the company
        company_np_growth_3y = None
        if not df_growth.empty and "Net Profit" in df_growth.columns:
            np_growth = df_growth["Net Profit"].pct_change() * 100
            recent_np_growth = np_growth.dropna().tail(3)
            if not recent_np_growth.empty:
                company_np_growth_3y = float(recent_np_growth.mean())

        # Peer averages (last 3 years, matching the company metric)
        peer_rev_growth = _peer_avg_last3(peer_summaries, "Last_3_years_Growth_Per")
        peer_opm = _peer_avg_last3(peer_summaries, "Last_3_Years_Operating_Margin")
        peer_npm = _peer_avg_last3(peer_summaries, "Last_3_Years_Net_Profit_Margin")

        comparison_rows = [
            {
                "Metric": "Revenue Trend",
                "Company": financial_summary.get("Revenue_Trend") or "N/A",
                "Peers (Avg)": "-",
                "Comparison": "-",
            },
            {
                "Metric": "Net Profit Trend",
                "Company": financial_summary.get("Net_Profit_Trend") or "N/A",
                "Peers (Avg)": "-",
                "Comparison": "-",
            },
            {
                "Metric": "3 Years Revenue Growth",
                "Company": _fmt_pct(company_rev_growth),
                "Peers (Avg)": _fmt_pct(peer_rev_growth),
                "Comparison": _delta(company_rev_growth, peer_rev_growth),
            },
            {
                "Metric": "3 Year Net Profit Growth",
                "Company": _fmt_pct(company_np_growth_3y),
                "Peers (Avg)": "-",
                "Comparison": "-",
            },
            {
                "Metric": "3 Years Average Operating Profit Margin",
                "Company": _fmt_pct(company_opm),
                "Peers (Avg)": _fmt_pct(peer_opm),
                "Comparison": _delta(company_opm, peer_opm),
            },
            {
                "Metric": "3 Years Net Profit Margin",
                "Company": _fmt_pct(company_npm),
                "Peers (Avg)": _fmt_pct(peer_npm),
                "Comparison": _delta(company_npm, peer_npm),
            },
            {
                "Metric": "3 Years Revenue Growth Compared to peers Revenue Growth %",
                "Company": _fmt_pct(company_rev_growth),
                "Peers (Avg)": _fmt_pct(peer_rev_growth),
                "Comparison": _delta(company_rev_growth, peer_rev_growth),
            },
            {
                "Metric": "3 Year Avg Operating Margin compared to Peers Operating Margin",
                "Company": _fmt_pct(company_opm),
                "Peers (Avg)": _fmt_pct(peer_opm),
                "Comparison": _delta(company_opm, peer_opm),
            },
            {
                "Metric": "3 Years Avg Profit Margin compared to Peers Net Profit Margin",
                "Company": _fmt_pct(company_npm),
                "Peers (Avg)": _fmt_pct(peer_npm),
                "Comparison": _delta(company_npm, peer_npm),
            },
        ]

        with st.expander("Peer vs Company Comparison", expanded=False):
            st.dataframe(
                pd.DataFrame(comparison_rows),
                hide_index=True,
                use_container_width=True,
            )

        # ======================================================
        # FINANCIAL SUMMARY JSON
        # ======================================================

        with st.expander(
            "Financial Summary JSON",
            expanded=False
        ):

            st.json(
                financial_summary,
                expanded=False
            )

        # ======================================================
        # SCREENER COMPANY INFORMATION
        # ======================================================

        with st.expander(
            "Company Information",
            expanded=False
        ):

            if not screener_info:

                st.info(
                    "Company information not available."
                )

            else:

                st.markdown(
                    f"**{screener_info['company_name']}** "
                    f"({screener_info['symbol']})"
                )

                # --------------------------------------------------
                # About
                # --------------------------------------------------

                if screener_info["about"]:

                    st.markdown("#### About")

                    st.write(
                        screener_info["about"]
                    )

                # --------------------------------------------------
                # Key Points
                # --------------------------------------------------

                if screener_info["key_points"]:
                    logger.info(screener_info["key_points"])

                    st.markdown("#### Key Points")

                    for number, point in enumerate(
                        screener_info["key_points"],
                        start=1
                    ):

                        title = point.get("title", "")
                        description = point.get(
                            "description",
                            ""
                        )

                        if title:
                            st.markdown(
                                f"**{number}. {title}**"
                            )
                        else:
                            st.markdown(
                                f"**{number}.**"
                            )

                        if description:
                            st.write(description)

                # --------------------------------------------------
                # Nothing found on the page
                # --------------------------------------------------

                if (
                    not screener_info["about"]
                    and not screener_info["key_points"]
                ):

                    st.info(
                        "No About or Key Points text "
                        "found for this company."
                    )

    except Exception as e:

        logger.exception(
            f"Error while rendering UI for {ticker_input}"
        )

        st.error(
            f"Error displaying stock information: {e}"
        )


if __name__ == "__main__":
    main()

    
# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

st.caption(
    "Built Using Streamlit + Yahoo Finance"
)

logger.info(f"Application Finished \n \n{'#'*50}")

