"""FP&A forecast page."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.charts import waterfall
from dashboard.utils.data import load_dashboard_data
from dashboard.utils.formatting import fmt_currency, money_columns


def render(data) -> None:
    st.title("FP&A Forecast")
    c1, c2, c3 = st.columns(3)
    utilisation = c1.slider("Utilisation %", min_value=0.1, max_value=1.0, value=0.72, step=0.01)
    days = c2.number_input("Days in month", min_value=1, max_value=31, value=26, step=1)
    rate_adj = c3.number_input("Rate adjustment %", min_value=-30.0, max_value=30.0, value=0.0, step=0.5)

    refreshed = load_dashboard_data(f"{data.period:%Y-%m-%d}", utilisation, int(days), rate_adj)
    variance = refreshed.forecast_variance
    st.dataframe(money_columns(variance, ["forecast_revenue", "actual_revenue", "variance_amount", "utilisation_variance", "rate_variance", "mix_variance"]), use_container_width=True, hide_index=True)

    totals = variance[["forecast_revenue", "actual_revenue", "utilisation_variance", "rate_variance", "mix_variance"]].sum()
    labels = ["Forecast", "Utilisation", "Rate", "Mix", "Actual"]
    values = [
        int(totals["forecast_revenue"]),
        int(totals["utilisation_variance"]),
        int(totals["rate_variance"]),
        int(totals["mix_variance"]),
        int(totals["actual_revenue"]),
    ]
    st.plotly_chart(waterfall(labels, values, "Forecast to actual bridge"), use_container_width=True)

    gap = int(totals["actual_revenue"] - totals["forecast_revenue"])
    driver = variance[["utilisation_variance", "rate_variance", "mix_variance"]].sum().abs().idxmax().replace("_", " ")
    direction = "above" if gap >= 0 else "below"
    st.markdown(
        f"<div class='info-band'>Revenue was {fmt_currency(abs(gap))} {direction} forecast due to the largest movement in {driver}.</div>",
        unsafe_allow_html=True,
    )
