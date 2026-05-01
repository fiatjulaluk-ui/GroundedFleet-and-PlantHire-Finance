"""Main entry point for the Grounded Finance Dashboard."""

from __future__ import annotations

import importlib
import os
import sys

# Ensure the repo root is in the Python path so imports work on Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from dashboard.utils.data import available_periods, load_dashboard_data
from dashboard.utils.formatting import BRAND


PAGES = {
    "Executive Dashboard": "dashboard.pages.01_overview",
    "Revenue Engine": "dashboard.pages.02_revenue",
    "WIP and Billing": "dashboard.pages.03_wip",
    "Job and Asset Profit": "dashboard.pages.04_profitability",
    "FP&A Forecast": "dashboard.pages.05_forecast",
    "BAS and Tax": "dashboard.pages.06_compliance",
    "Journal Pack": "dashboard.pages.07_journals",
    "Exception Log": "dashboard.pages.08_exceptions",
}


def _css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {BRAND['background']}; color: {BRAND['text']}; }}
        h1, h2, h3, h4, h5, h6, p, label, span {{ font-family: Arial, sans-serif; }}
        [data-testid="stMetric"] {{
            background: white;
            border: 1px solid rgba(44,44,42,0.08);
            border-left: 4px solid {BRAND['primary']};
            padding: 0.85rem;
            border-radius: 8px;
        }}
        .logo-box {{
            border: 2px dashed {BRAND['sage']};
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            color: {BRAND['primary']};
            font-weight: 800;
            margin-bottom: 1rem;
        }}
        .info-band {{
            background: white;
            border-left: 5px solid {BRAND['primary']};
            padding: 0.9rem 1rem;
            border-radius: 8px;
        }}
        .warn-band {{
            background: #fff7ea;
            border-left: 5px solid {BRAND['warning']};
            padding: 0.9rem 1rem;
            border-radius: 8px;
        }}
        .error-band {{
            background: #fff0f0;
            border-left: 5px solid {BRAND['error']};
            padding: 0.9rem 1rem;
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Grounded Finance Dashboard", layout="wide")
    _css()

    periods = available_periods()
    default_idx = len(periods) - 1 if periods else 0

    with st.sidebar:
        st.markdown("<div class='logo-box'>GROUNDED<br>FLEET & PLANT<br>HIRE FINANCE</div>", unsafe_allow_html=True)
        entity = st.selectbox("Entity", ["Grounded Fleet Hire Pty Ltd"])
        period_label = st.selectbox("Period", periods, index=default_idx, format_func=lambda x: pd.to_datetime(x).strftime("%B %Y"))
        page_name = st.radio("Navigation", list(PAGES.keys()))

    if st.session_state.get("period_label") != period_label:
        st.session_state["period_label"] = period_label

    data = load_dashboard_data(period_label)
    st.session_state["dashboard_data"] = data

    st.caption(f"{entity} | {pd.to_datetime(period_label).strftime('%B %Y')} | Data source: {data.source}")
    module = importlib.import_module(PAGES[page_name])
    module.render(data)


if __name__ == "__main__":
    main()
