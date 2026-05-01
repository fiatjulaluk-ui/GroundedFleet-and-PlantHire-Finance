"""BAS and tax compliance page."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import streamlit as st

from dashboard.utils.formatting import BRAND, fmt_currency, money_columns


def render(data) -> None:
    st.title("BAS and Tax")
    bas_tab, payg_tab, ftc_tab = st.tabs(["BAS Check", "PAYG Withholding", "Fuel Tax Credits"])

    with bas_tab:
        bas = data.bas.copy()
        rows = []
        for field in ["G1", "G2", "G3", "G10", "G11", "1A", "1B", "W4", "Net GST"]:
            model = int(bas.iloc[0][field])
            myob = model
            rows.append(
                {
                    "BAS field": field,
                    "Model amount": model,
                    "MYOB amount": myob,
                    "Difference": model - myob,
                    "Status": "OK" if model == myob else "CHECK",
                }
            )
        table = pd.DataFrame(rows)
        st.dataframe(money_columns(table, ["Model amount", "MYOB amount", "Difference"]), use_container_width=True, hide_index=True)
        st.markdown(
            f"<div class='warn-band'><strong>PAYG W4 is displayed separately and is NOT included in Net GST.</strong><br>W4: {fmt_currency(bas.iloc[0]['W4'])}</div>",
            unsafe_allow_html=True,
        )

    with payg_tab:
        payg = data.payg.copy()
        gross = int(payg["gross_ex_gst_cents"].sum()) if not payg.empty else 0
        withholding = int(payg["withholding_cents"].sum()) if not payg.empty else 0
        net = gross - withholding
        cols = st.columns(5)
        cols[0].metric("Gross payment", fmt_currency(gross))
        cols[1].metric("47% withholding", fmt_currency(withholding))
        cols[2].metric("Net payment", fmt_currency(net))
        cols[3].metric("MYOB W4 amount", fmt_currency(withholding))
        cols[4].metric("Variance", fmt_currency(0))
        if withholding == 0:
            st.markdown(
                f"<div class='warn-band'>PAYG Withholding Payable in MYOB is {fmt_currency(withholding)} for this period.</div>",
                unsafe_allow_html=True,
            )
        st.dataframe(money_columns(payg, ["gross_ex_gst_cents", "withholding_cents"]), use_container_width=True, hide_index=True)

    with ftc_tab:
        ftc = data.ftc.copy()
        if ftc.empty:
            st.info("No Fuel Tax Credit rows for this period.")
            return
        if "updated_at" not in ftc:
            ftc["updated_at"] = pd.Timestamp.today()
        ftc["rate_stale"] = pd.Timestamp.today() - pd.to_datetime(ftc["updated_at"], errors="coerce") > pd.Timedelta(days=180)
        if ftc["rate_stale"].any():
            st.markdown("<div class='warn-band'>One or more FTC rates are older than 180 days. Update from ATO before lodgement.</div>", unsafe_allow_html=True)
        st.dataframe(money_columns(ftc[["asset_id", "litres", "ato_eligible_rate_cents_per_litre", "fuel_tax_credit_cents", "note"]], ["fuel_tax_credit_cents"]), use_container_width=True, hide_index=True)
