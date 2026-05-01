"""WIP and billing page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.utils.charts import wip_bar
from dashboard.utils.formatting import BRAND, money_columns


def render(data) -> None:
    st.title("WIP and Billing")
    wip = data.wip.groupby(["job_id", "customer_name"], as_index=False).agg(
        earned=("earned_revenue_cents", "sum"),
        invoiced=("invoiced_amount_cents", "sum"),
        WIP=("wip_cents", "sum"),
        age_days=("age_days", "max"),
    )
    wip["status"] = wip.apply(
        lambda r: "Aged" if r["WIP"] > 0 and r["age_days"] > 30 else ("Open" if r["WIP"] > 0 else "OK"),
        axis=1,
    )

    chart_df = wip.groupby("customer_name", as_index=False)["WIP"].sum().sort_values("WIP", ascending=False)
    st.plotly_chart(wip_bar(chart_df, "customer_name", "WIP", "WIP by customer"), use_container_width=True)

    def age_style(value):
        return f"background-color: {BRAND['error']}; color: white" if value == "Aged" else ""

    display = money_columns(wip, ["earned", "invoiced", "WIP"])
    st.dataframe(display.style.map(age_style, subset=["status"]), use_container_width=True, hide_index=True)

    st.subheader("Billing actions")
    candidates = wip[wip["WIP"] > 0].sort_values("WIP", ascending=False)
    if candidates.empty:
        st.success("No positive WIP requiring invoice action.")
        return
    selected = st.selectbox("Select job to raise invoice", candidates["job_id"].tolist())
    row = candidates[candidates["job_id"] == selected].iloc[0]
    if st.button("Raise Invoice"):
        with st.modal("Invoice details"):
            st.write(f"Job: {row['job_id']}")
            st.write(f"Customer: {row['customer_name']}")
            st.write(f"Unbilled amount: ${row['WIP'] / 100:,.2f}")
            st.write("No MYOB API call was made.")
