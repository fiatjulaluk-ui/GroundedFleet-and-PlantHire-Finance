"""Revenue engine page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.utils.data import excel_bytes
from dashboard.utils.formatting import BRAND, fmt_currency, money_columns


def _status_style(value):
    colour = {
        "OK": BRAND["primary"],
        "Underbilled": BRAND["warning"],
        "Overbilled": BRAND["error"],
        "No Invoice": "#777772",
    }.get(value, "#777772")
    return f"background-color: {colour}; color: white"


def render(data) -> None:
    st.title("Revenue Engine")
    revenue = data.revenue.merge(
        data.wip[["job_id", "asset_id", "invoiced_amount_cents", "wip_cents", "status"]],
        on=["job_id", "asset_id"],
        how="left",
    )
    usage = data.tables["usage_log"][["usage_id", "hours_worked"]]
    revenue = revenue.merge(usage, on="usage_id", how="left")

    c1, c2, c3, c4 = st.columns(4)
    min_date = revenue["usage_date"].min().date() if not revenue.empty else data.period
    max_date = revenue["usage_date"].max().date() if not revenue.empty else data.period
    date_range = c1.date_input("Date range", value=(min_date, max_date))
    job = c2.selectbox("Job", ["All"] + sorted(revenue["job_id"].dropna().unique().tolist()))
    asset = c3.selectbox("Asset", ["All"] + sorted(revenue["asset_id"].dropna().unique().tolist()))
    status = c4.selectbox("Exception status", ["All", "OK", "Underbilled", "Overbilled", "No Invoice"])

    filtered = revenue.copy()
    if len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered = filtered[(filtered["usage_date"] >= start) & (filtered["usage_date"] <= end)]
    if job != "All":
        filtered = filtered[filtered["job_id"] == job]
    if asset != "All":
        filtered = filtered[filtered["asset_id"] == asset]
    if status != "All":
        filtered = filtered[filtered["status"] == status]

    cols = st.columns(3)
    cols[0].metric("Total Earned", fmt_currency(filtered["total_revenue_cents"].sum()))
    cols[1].metric("Total Invoiced", fmt_currency(filtered["invoiced_amount_cents"].fillna(0).sum()))
    cols[2].metric("Total WIP", fmt_currency(filtered["wip_cents"].fillna(0).sum()))

    table = filtered.rename(
        columns={
            "usage_date": "date",
            "job_id": "job",
            "asset_id": "asset",
            "rate_used_cents": "rate_used",
            "float_applied_cents": "float_fee",
            "total_revenue_cents": "total_revenue",
            "invoiced_amount_cents": "invoiced",
            "wip_cents": "WIP",
        }
    )[["date", "job", "asset", "hours_worked", "billable_hours", "rate_used", "hire_revenue_cents", "float_fee", "total_revenue", "invoiced", "WIP", "status"]]
    table = table.rename(columns={"hire_revenue_cents": "hire_revenue"})
    display = money_columns(table, ["rate_used", "hire_revenue", "float_fee", "total_revenue", "invoiced", "WIP"])
    st.dataframe(display.style.map(_status_style, subset=["status"]), use_container_width=True, hide_index=True)

    st.download_button(
        "Export revenue to Excel",
        data=excel_bytes({"Revenue": table}),
        file_name=f"revenue_engine_{data.period:%Y_%m}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
