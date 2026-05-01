"""Exception log page."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import streamlit as st

from dashboard.utils.data import excel_bytes
from dashboard.utils.formatting import BRAND


def render(data) -> None:
    st.title("Exception Log")
    exceptions = data.exceptions.copy()
    if "resolved_ids" not in st.session_state:
        st.session_state["resolved_ids"] = set()
    if not exceptions.empty:
        exceptions["exception_id"] = [f"EXC{i:05d}" for i in range(1, len(exceptions) + 1)]
        exceptions.loc[exceptions["exception_id"].isin(st.session_state["resolved_ids"]), "status"] = "Resolved"

    high = len(exceptions[exceptions["severity"] == "HIGH"]) if not exceptions.empty else 0
    medium = len(exceptions[exceptions["severity"] == "MEDIUM"]) if not exceptions.empty else 0
    low = len(exceptions[exceptions["severity"] == "LOW"]) if not exceptions.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='error-band'><strong>HIGH</strong><br>{high}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='warn-band'><strong>MEDIUM</strong><br>{medium}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='info-band'><strong>LOW</strong><br>{low}</div>", unsafe_allow_html=True)

    if exceptions.empty:
        st.success("No exceptions detected.")
        return

    f1, f2, f3 = st.columns(3)
    severity = f1.multiselect("Severity", sorted(exceptions["severity"].unique()), default=sorted(exceptions["severity"].unique()))
    source = f2.multiselect("Source module", sorted(exceptions["source"].unique()), default=sorted(exceptions["source"].unique()))
    status = f3.multiselect("Status", sorted(exceptions["status"].unique()), default=sorted(exceptions["status"].unique()))
    filtered = exceptions[
        exceptions["severity"].isin(severity)
        & exceptions["source"].isin(source)
        & exceptions["status"].isin(status)
    ]
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    selected = st.selectbox("Exception to resolve", filtered["exception_id"].tolist() if not filtered.empty else [])
    if st.button("Mark as Resolved", disabled=not selected):
        st.session_state["resolved_ids"].add(selected)
        st.success(f"{selected} marked as resolved in the dashboard session.")
        st.rerun()

    st.download_button(
        "Export exceptions to Excel",
        data=excel_bytes({"Exceptions": filtered}),
        file_name=f"exceptions_{data.period:%Y_%m}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
