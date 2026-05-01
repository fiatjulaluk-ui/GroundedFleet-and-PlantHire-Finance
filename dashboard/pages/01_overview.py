"""Executive dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.utils.charts import revenue_bar, trend_line
from dashboard.utils.formatting import BRAND, fmt_currency, fmt_pct, money_columns, status_badge


def render(data) -> None:
    st.title("Executive Dashboard")

    revenue = data.revenue
    invoices = data.invoices
    wip_total = int(data.wip["wip_cents"].clip(lower=0).sum()) if not data.wip.empty else 0
    total_revenue = int(revenue["total_revenue_cents"].sum()) if not revenue.empty else 0
    invoiced = int(invoices["amount_ex_gst_cents"].sum()) if not invoices.empty else 0
    costs = data.tables["costs"]
    period_costs = costs[(costs["cost_date"].dt.to_period("M") == pd.Timestamp(data.period).to_period("M"))]
    total_cost = int(period_costs["amount_cents"].sum()) if not period_costs.empty else 0
    profit = total_revenue - total_cost
    margin = 0 if total_revenue == 0 else profit / total_revenue * 100

    cols = st.columns(6)
    cols[0].metric("Revenue Earned", fmt_currency(total_revenue))
    cols[1].metric("MYOB Invoiced", fmt_currency(invoiced))
    cols[2].metric("WIP Unbilled", fmt_currency(wip_total))
    cols[3].metric("Total Cost", fmt_currency(total_cost))
    cols[4].metric("Profit", fmt_currency(profit))
    cols[5].metric("Margin %", fmt_pct(margin))

    high = len(data.exceptions[data.exceptions["severity"] == "HIGH"]) if not data.exceptions.empty else 0
    journal_status = "BALANCED" if not data.journals.empty else "CHECK"
    bas_status = "OK" if int(data.bas.iloc[0]["Net GST"]) >= 0 else "CHECK"
    c1, c2, c3 = st.columns(3)
    c1.metric("Open Exceptions (HIGH severity)", high)
    c2.markdown(status_badge(f"Journal {journal_status}"), unsafe_allow_html=True)
    c3.markdown(status_badge(f"BAS {bas_status}"), unsafe_allow_html=True)

    trend = data.tables["revenue_engine"].copy()
    trend["month"] = trend["usage_date"].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby("month", as_index=False)["total_revenue_cents"].sum()
    by_type = revenue.groupby("equipment_type", as_index=False)["total_revenue_cents"].sum().sort_values("total_revenue_cents")

    left, right = st.columns(2)
    left.plotly_chart(trend_line(trend, "month", "total_revenue_cents", "Monthly revenue trend"), use_container_width=True)
    right.plotly_chart(revenue_bar(by_type, "total_revenue_cents", "equipment_type", "Revenue by equipment type", orientation="h"), use_container_width=True)

    top_jobs = (
        revenue.groupby("job_id", as_index=False)["total_revenue_cents"].sum()
        .merge(data.tables["job_master"][["job_id", "customer_name"]], on="job_id", how="left")
        .sort_values("total_revenue_cents", ascending=False)
        .head(5)
    )
    top_jobs = money_columns(top_jobs.rename(columns={"total_revenue_cents": "revenue"}), ["revenue"])

    st.subheader("Top 5 jobs by revenue")
    st.dataframe(top_jobs, use_container_width=True, hide_index=True)

    st.subheader("Exception summary by severity")
    if data.exceptions.empty:
        st.success("No open exceptions for the selected period.")
    else:
        summary = data.exceptions.groupby("severity", as_index=False).size().rename(columns={"size": "count"})
        styled = summary.style.map(
            lambda _: f"background-color: {BRAND['error']}; color: white" if _ == "HIGH" else (
                f"background-color: {BRAND['warning']}; color: white" if _ == "MEDIUM" else ""
            ),
            subset=["severity"],
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)
