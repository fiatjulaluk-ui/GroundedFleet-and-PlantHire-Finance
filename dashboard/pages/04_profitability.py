"""Job and asset profitability page."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.charts import profit_scatter, revenue_bar
from dashboard.utils.formatting import colour_margin, money_columns


def render(data) -> None:
    st.title("Job and Asset Profit")
    tab_job, tab_asset = st.tabs(["By Job", "By Asset"])

    with tab_job:
        jobs = data.job_profit.copy()
        table = money_columns(jobs[["job_id", "customer", "revenue", "total_cost", "profit", "margin_pct"]], ["revenue", "total_cost", "profit"])
        styled = table.style.map(lambda v: f"color: {colour_margin(v)}; font-weight: 700", subset=["margin_pct"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.plotly_chart(
            profit_scatter(jobs, "revenue", "margin_pct", "total_cost", color="customer", title="Revenue vs margin"),
            use_container_width=True,
        )

    with tab_asset:
        assets = data.asset_profit.copy()
        table = assets[["asset_id", "equipment_type", "revenue", "total_cost", "profit", "hours", "rev_per_hour"]].rename(
            columns={"total_cost": "cost"}
        )
        st.dataframe(money_columns(table, ["revenue", "cost", "profit", "rev_per_hour"]), use_container_width=True, hide_index=True)
        chart = assets.copy()
        chart["profit_per_hour"] = chart["profit"] / chart["hours"].replace(0, 1)
        st.plotly_chart(revenue_bar(chart.sort_values("profit_per_hour"), "profit_per_hour", "asset_id", "Profit per hour by asset", orientation="h"), use_container_width=True)
