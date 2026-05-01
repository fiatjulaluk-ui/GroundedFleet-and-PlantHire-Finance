"""Journal pack page."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.formatting import fmt_currency, money_columns


def render(data) -> None:
    st.title("Journal Pack")
    journals = data.journals.copy()
    dr_total = int(journals["amount_cents"].sum())
    cr_total = int(journals["amount_cents"].sum())
    balanced = dr_total == cr_total
    if balanced:
        st.markdown("<div class='info-band'><strong>BALANCED</strong></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='error-band'><strong>IMBALANCED - DO NOT POST</strong></div>", unsafe_allow_html=True)

    st.dataframe(money_columns(journals, ["amount_cents"]), use_container_width=True, hide_index=True)

    st.subheader("Payroll compliance")
    payroll = data.payroll.copy()
    super_expected = int(payroll["expected_super_cents"].sum()) if not payroll.empty else 0
    super_paid = int(payroll["super_guarantee_cents"].sum()) if not payroll.empty else 0
    tax_expected = int(payroll["expected_payroll_tax_cents"].sum()) if not payroll.empty else 0
    tax_paid = int(payroll["payroll_tax_cents"].sum()) if not payroll.empty else 0
    coinvest = int(payroll["coinvest_cents"].sum()) if not payroll.empty else 0
    cols = st.columns(3)
    cols[0].metric("Super expected vs paid", f"{fmt_currency(super_expected)} / {fmt_currency(super_paid)}")
    cols[1].metric("Payroll tax expected vs MYOB", f"{fmt_currency(tax_expected)} / {fmt_currency(tax_paid)}")
    cols[2].metric("CoINVEST status", "Pending" if coinvest == 0 else fmt_currency(coinvest))
    st.dataframe(money_columns(payroll, ["gross_wages_cents", "expected_super_cents", "super_guarantee_cents", "expected_payroll_tax_cents", "payroll_tax_cents", "coinvest_cents"]), use_container_width=True, hide_index=True)

    if st.button("Post to MYOB"):
        st.info("Coming soon: MYOB Advanced API integration")
