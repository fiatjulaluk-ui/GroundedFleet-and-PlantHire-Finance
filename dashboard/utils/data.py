"""Dashboard data loading with DB-first and CSV fallback behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
CSV_DIR = ROOT / "data" / "csv"


MONEY_COLUMNS = {
    "amount_cents",
    "gst_input_cents",
    "bas_g11_cents",
    "bas_1b_cents",
    "withholding_cents",
    "amount_ex_gst_cents",
    "gst_cents",
    "amount_inc_gst_cents",
    "hourly_rate_cents",
    "float_fee_cents",
    "override_rate_cents",
    "standard_rate_cents",
    "hire_revenue_cents",
    "float_applied_cents",
    "total_revenue_cents",
    "gst_output_cents",
    "bas_g1_cents",
    "bas_1a_cents",
    "gross_wages_cents",
    "super_guarantee_cents",
    "payroll_tax_cents",
    "coinvest_cents",
    "fuel_tax_credit_cents",
    "fuel_cost_cents",
}


@dataclass
class DashboardData:
    period: date
    source: str
    tables: dict[str, pd.DataFrame]
    revenue: pd.DataFrame
    invoices: pd.DataFrame
    wip: pd.DataFrame
    job_profit: pd.DataFrame
    asset_profit: pd.DataFrame
    bas: pd.DataFrame
    payg: pd.DataFrame
    payroll: pd.DataFrame
    ftc: pd.DataFrame
    exceptions: pd.DataFrame
    journals: pd.DataFrame
    forecast_variance: pd.DataFrame


def _read_csv(name: str) -> pd.DataFrame:
    path = CSV_DIR / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    for col in df.columns:
        if col.endswith("_date") or col.endswith("_start") or col in {"effective_from", "effective_to"}:
            df[col] = pd.to_datetime(df[col], errors="coerce")
        if col in MONEY_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def _month_bounds(period: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(period).replace(day=1)
    end = start + pd.offsets.MonthEnd(1)
    return start, end


def _period_filter(df: pd.DataFrame, date_col: str, period: date) -> pd.DataFrame:
    if df.empty or date_col not in df:
        return df.copy()
    start, end = _month_bounds(period)
    return df[(df[date_col] >= start) & (df[date_col] <= end)].copy()


def _csv_tables() -> dict[str, pd.DataFrame]:
    names = [
        "rate_card",
        "fleet_register",
        "job_master",
        "usage_log",
        "job_rates",
        "revenue_engine",
        "costs",
        "invoice_myob",
        "payroll_config",
        "payroll_monthly",
        "payg_withholding",
        "fuel_tax_credit",
        "exception_log",
    ]
    return {name: _read_csv(name) for name in names}


def _build_wip(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    revenue = tables["revenue_engine"]
    invoices = tables["invoice_myob"]
    jobs = tables["job_master"][["job_id", "customer_name", "site_name", "end_date"]]
    fleet = tables["fleet_register"][["asset_id", "equipment_type"]]
    earned = revenue.groupby(["job_id", "asset_id"], as_index=False)["total_revenue_cents"].sum()
    earned = earned.rename(columns={"total_revenue_cents": "earned_revenue_cents"})
    invoiced = invoices.groupby(["job_id", "asset_id"], as_index=False)["amount_ex_gst_cents"].sum()
    invoiced = invoiced.rename(columns={"amount_ex_gst_cents": "invoiced_amount_cents"})
    wip = earned.merge(invoiced, on=["job_id", "asset_id"], how="left")
    wip["invoiced_amount_cents"] = wip["invoiced_amount_cents"].fillna(0).astype(int)
    wip["wip_cents"] = wip["earned_revenue_cents"] - wip["invoiced_amount_cents"]
    wip = wip.merge(jobs, on="job_id", how="left").merge(fleet, on="asset_id", how="left")
    wip["status"] = wip.apply(_billing_status, axis=1)
    today = pd.Timestamp(date.today())
    wip["age_days"] = (today - wip["end_date"]).dt.days.fillna(0).astype(int)
    return wip


def _billing_status(row: pd.Series) -> str:
    if int(row.get("invoiced_amount_cents", 0)) == 0:
        return "No Invoice"
    variance = int(row.get("wip_cents", 0))
    if variance > 50_000:
        return "Underbilled"
    if variance < -50_000:
        return "Overbilled"
    return "OK"


def _build_profit(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    revenue = tables["revenue_engine"]
    costs = tables["costs"]
    jobs = tables["job_master"]
    fleet = tables["fleet_register"]

    job_rev = revenue.groupby("job_id", as_index=False)["total_revenue_cents"].sum().rename(
        columns={"total_revenue_cents": "revenue"}
    )
    job_cost = _cost_pivot(costs, "job_id")
    job_profit = jobs[["job_id", "customer_name"]].merge(job_rev, on="job_id", how="left").merge(job_cost, on="job_id", how="left")
    job_profit = _profit_columns(job_profit).rename(columns={"customer_name": "customer"})

    asset_rev = revenue.groupby("asset_id", as_index=False)["total_revenue_cents"].sum().rename(
        columns={"total_revenue_cents": "revenue"}
    )
    asset_cost = _cost_pivot(costs[costs["asset_id"].notna()], "asset_id")
    hours = tables["usage_log"].groupby("asset_id", as_index=False)["hours_worked"].sum().rename(columns={"hours_worked": "hours"})
    asset_profit = (
        fleet[["asset_id", "equipment_type"]]
        .merge(asset_rev, on="asset_id", how="left")
        .merge(asset_cost, on="asset_id", how="left")
        .merge(hours, on="asset_id", how="left")
    )
    asset_profit = _profit_columns(asset_profit)
    asset_profit["rev_per_hour"] = asset_profit["revenue"] / asset_profit["hours"].replace(0, pd.NA)
    asset_profit["rev_per_hour"] = asset_profit["rev_per_hour"].fillna(0).astype(int)
    return job_profit, asset_profit


def _cost_pivot(costs: pd.DataFrame, index: str) -> pd.DataFrame:
    pivot = costs.pivot_table(index=index, columns="cost_category", values="amount_cents", aggfunc="sum", fill_value=0).reset_index()
    out = pd.DataFrame({index: pivot[index]})
    out["fuel_cost"] = pivot.get("Fuel", 0)
    out["labour_cost"] = pivot.get("Labour", 0)
    out["maintenance_cost"] = pivot.get("Maintenance", 0)
    out["transport_cost"] = pivot.get("Transport/float", 0)
    known = {"Fuel", "Labour", "Maintenance", "Transport/float"}
    other_cols = [col for col in pivot.columns if col not in known | {index}]
    out["other_cost"] = pivot[other_cols].sum(axis=1) if other_cols else 0
    out["total_cost"] = out[["fuel_cost", "labour_cost", "maintenance_cost", "transport_cost", "other_cost"]].sum(axis=1)
    return out


def _profit_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.fillna(0).copy()
    for col in ["revenue", "fuel_cost", "labour_cost", "maintenance_cost", "transport_cost", "other_cost", "total_cost"]:
        if col not in out:
            out[col] = 0
        out[col] = out[col].astype(int)
    out["profit"] = out["revenue"] - out["total_cost"]
    out["margin_pct"] = (out["profit"] / out["revenue"].replace(0, pd.NA) * 100).fillna(0).round(2)
    return out


def _build_bas(tables: dict[str, pd.DataFrame], period: date) -> pd.DataFrame:
    start, _ = _month_bounds(period)
    revenue = _period_filter(tables["revenue_engine"], "usage_date", period)
    costs = _period_filter(tables["costs"], "cost_date", period)
    payg = _payg_for_period(tables, period)
    one_a = int(revenue["bas_1a_cents"].sum()) if not revenue.empty else 0
    one_b = int(costs["bas_1b_cents"].sum()) if not costs.empty else 0
    return pd.DataFrame(
        [
            {
                "period": start,
                "G1": int(revenue["bas_g1_cents"].sum()) if not revenue.empty else 0,
                "G2": 0,
                "G3": 0,
                "G10": 0,
                "G11": int(costs["bas_g11_cents"].sum()) if not costs.empty else 0,
                "1A": one_a,
                "1B": one_b,
                "W4": int(payg["withholding_cents"].sum()) if not payg.empty else 0,
                "Net GST": one_a - one_b,
            }
        ]
    )


def _payg_for_period(tables: dict[str, pd.DataFrame], period: date) -> pd.DataFrame:
    payg = tables["payg_withholding"]
    costs = tables["costs"][["cost_id", "cost_date"]]
    if payg.empty:
        return payg.copy()
    merged = payg.merge(costs, on="cost_id", how="left")
    return _period_filter(merged, "cost_date", period)


def _payroll_for_period(tables: dict[str, pd.DataFrame], period: date) -> pd.DataFrame:
    payroll = tables["payroll_monthly"].copy()
    if payroll.empty:
        return payroll
    start, _ = _month_bounds(period)
    payroll = payroll[payroll["month_start"] == start].copy()
    gross_total = payroll["gross_wages_cents"].sum()
    threshold = 8_333_300
    tax_rate = 0.0485
    payroll["expected_super_cents"] = (payroll["gross_wages_cents"] * 0.12).round().astype(int)
    expected_tax_total = max(gross_total - threshold, 0) * tax_rate
    payroll["expected_payroll_tax_cents"] = (
        expected_tax_total * payroll["gross_wages_cents"] / gross_total if gross_total else 0
    ).round().astype(int)
    payroll["expected_coinvest_cents"] = 0
    payroll["super_variance_cents"] = payroll["super_guarantee_cents"] - payroll["expected_super_cents"]
    payroll["payroll_tax_variance_cents"] = payroll["payroll_tax_cents"] - payroll["expected_payroll_tax_cents"]
    payroll["coinvest_variance_cents"] = payroll["coinvest_cents"] - payroll["expected_coinvest_cents"]
    return payroll


def _build_journals(tables: dict[str, pd.DataFrame], period: date, wip: pd.DataFrame) -> pd.DataFrame:
    costs = _period_filter(tables["costs"], "cost_date", period)
    payg = _payg_for_period(tables, period)
    wip_amount = int(wip["wip_cents"].clip(lower=0).sum()) if not wip.empty else 0
    cost_amount = int(costs["amount_cents"].sum()) if not costs.empty else 0
    depreciation = len(tables["fleet_register"]) * 750_000
    payg_amount = int(payg["withholding_cents"].sum()) if not payg.empty else 0
    specs = [
        ("JE001", "WIP Accrual", "Unbilled Revenue", "Hire Revenue", wip_amount, "Recognise earned unbilled revenue"),
        ("JE002", "Cost Accrual", "Operating Expense", "Accrued Expenses", cost_amount, "Accrue operating costs"),
        ("JE003", "Depreciation", "Depreciation Expense", "Accumulated Depreciation", depreciation, "Monthly fleet depreciation estimate"),
        ("JE004", "PAYG No-ABN", "Trade Payables", "PAYG Withholding Payable", payg_amount, "Move no-ABN withholding to W4 liability"),
    ]
    return pd.DataFrame(
        [
            {
                "journal_id": journal_id,
                "description": description,
                "dr_account": dr_account,
                "cr_account": cr_account,
                "amount_cents": amount,
                "status": "OK",
            }
            for journal_id, description, dr_account, cr_account, amount, note in specs
        ]
    )


def _build_exceptions(tables: dict[str, pd.DataFrame], wip: pd.DataFrame, journals: pd.DataFrame, payroll: pd.DataFrame, period: date) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in wip.itertuples(index=False):
        if row.invoiced_amount_cents == 0 and row.age_days > 14:
            rows.append(_issue("No invoice", "Revenue", f"{row.job_id}/{row.asset_id} has earned revenue and no invoice", "HIGH", "Raise invoice", "Open", period))
        elif row.wip_cents > 50_000:
            rows.append(_issue("Underbilling", "Revenue", f"{row.job_id}/{row.asset_id} underbilled by {row.wip_cents} cents", "HIGH", "Review MYOB invoice", "Open", period))
        elif row.wip_cents < -50_000:
            rows.append(_issue("Overbilling", "Revenue", f"{row.job_id}/{row.asset_id} overbilled by {abs(row.wip_cents)} cents", "HIGH", "Review credit note", "Open", period))

    abn = tables["costs"][tables["costs"]["tax_code"] == "ABN"]
    payg_costs = set(tables["payg_withholding"]["cost_id"]) if not tables["payg_withholding"].empty else set()
    for row in abn[~abn["cost_id"].isin(payg_costs)].itertuples(index=False):
        rows.append(_issue("No ABN withholding", "PAYG", f"{row.cost_id} missing W4 withholding", "HIGH", "Create withholding liability", "Open", period))

    valid_jobs = set(tables["job_master"]["job_id"])
    for row in tables["costs"][~tables["costs"]["job_id"].isin(valid_jobs)].itertuples(index=False):
        rows.append(_issue("Orphan cost", "Costs", f"{row.cost_id} references missing job {row.job_id}", "HIGH", "Fix job_id", "Open", period))

    if int(journals["amount_cents"].sum()) < 0:
        rows.append(_issue("Journal imbalance", "Journals", "Journal pack failed balance check", "HIGH", "Do not post", "Open", period))

    for row in payroll.itertuples(index=False):
        if abs(row.super_variance_cents) > 5_000 or abs(row.payroll_tax_variance_cents) > 5_000:
            rows.append(_issue("Payroll variance", "Payroll", f"{row.pay_group} variance exceeds configured tolerance", "MEDIUM", "Reconcile payroll reports", "Open", period))

    ftc = tables["fuel_tax_credit"].copy()
    if "updated_at" not in ftc:
        ftc["updated_at"] = pd.Timestamp.today()
    stale = ftc[pd.Timestamp.today() - pd.to_datetime(ftc["updated_at"], errors="coerce") > pd.Timedelta(days=180)]
    for row in stale.itertuples(index=False):
        rows.append(_issue("FTC rate stale", "FTC", f"{row.asset_id} FTC rate older than 180 days", "MEDIUM", "Update ATO rate", "Open", period))

    return pd.DataFrame(rows, columns=["issue_type", "source", "description", "severity", "suggested_action", "status", "period"])


def _issue(issue_type, source, description, severity, suggested_action, status, period):
    return {
        "issue_type": issue_type,
        "source": source,
        "description": description,
        "severity": severity,
        "suggested_action": suggested_action,
        "status": status,
        "period": period,
    }


def _forecast_variance(tables: dict[str, pd.DataFrame], period: date, utilisation_pct: float = 0.72, days: int | None = None, rate_adjustment_pct: float = 0.0) -> pd.DataFrame:
    revenue = _period_filter(tables["revenue_engine"], "usage_date", period)
    usage = _period_filter(tables["usage_log"], "usage_date", period)
    fleet = tables["fleet_register"]
    rate = tables["rate_card"][["equipment_type", "hourly_rate_cents"]]
    if days is None:
        start, end = _month_bounds(period)
        days = len(pd.bdate_range(start, end)) + sum(pd.date_range(start, end).weekday == 5)
    actual = revenue.groupby("equipment_type", as_index=False).agg(
        actual_revenue=("total_revenue_cents", "sum"),
        actual_hire_revenue=("hire_revenue_cents", "sum"),
        actual_hours=("billable_hours", "sum"),
        actual_rate=("rate_used_cents", "mean"),
    )
    forecast = fleet.merge(rate, on="equipment_type", how="left").groupby("equipment_type", as_index=False).agg(
        fleet_count=("asset_id", "count"), rate=("hourly_rate_cents", "mean")
    )
    forecast["forecast_hours"] = forecast["fleet_count"] * 9 * days * utilisation_pct
    forecast["forecast_rate"] = forecast["rate"] * (1 + rate_adjustment_pct / 100)
    forecast["forecast_revenue"] = (forecast["forecast_hours"] * forecast["forecast_rate"]).round().astype(int)
    out = forecast.merge(actual, on="equipment_type", how="left").fillna(0)
    out["actual_revenue"] = out["actual_revenue"].astype(int)
    out["variance_amount"] = out["actual_revenue"] - out["forecast_revenue"]
    out["variance_pct"] = (out["variance_amount"] / out["forecast_revenue"].replace(0, pd.NA) * 100).fillna(0).round(2)
    out["utilisation_variance"] = ((out["actual_hours"] - out["forecast_hours"]) * out["forecast_rate"]).round().astype(int)
    out["rate_variance"] = ((out["actual_rate"] - out["forecast_rate"]) * out["actual_hours"]).round().astype(int)
    out["mix_variance"] = (out["actual_hire_revenue"] - out["forecast_revenue"] - out["utilisation_variance"] - out["rate_variance"]).round().astype(int)
    return out[["equipment_type", "forecast_revenue", "actual_revenue", "variance_amount", "variance_pct", "utilisation_variance", "rate_variance", "mix_variance"]]


@st.cache_data(show_spinner=False)
def load_dashboard_data(period_label: str, utilisation_pct: float = 0.72, days: int | None = None, rate_adjustment_pct: float = 0.0) -> DashboardData:
    period = pd.to_datetime(period_label).date().replace(day=1)
    tables = _csv_tables()
    wip = _build_wip(tables)
    job_profit, asset_profit = _build_profit(tables)
    bas = _build_bas(tables, period)
    payg = _payg_for_period(tables, period)
    payroll = _payroll_for_period(tables, period)
    ftc = _period_filter(tables["fuel_tax_credit"], "month_start", period)
    journals = _build_journals(tables, period, wip)
    exceptions = _build_exceptions(tables, wip, journals, payroll, period)
    forecast_variance = _forecast_variance(tables, period, utilisation_pct, days, rate_adjustment_pct)
    return DashboardData(
        period=period,
        source="CSV fallback",
        tables=tables,
        revenue=_period_filter(tables["revenue_engine"], "usage_date", period),
        invoices=_period_filter(tables["invoice_myob"], "invoice_date", period),
        wip=wip,
        job_profit=job_profit,
        asset_profit=asset_profit,
        bas=bas,
        payg=payg,
        payroll=payroll,
        ftc=ftc,
        exceptions=exceptions,
        journals=journals,
        forecast_variance=forecast_variance,
    )


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buffer.getvalue()


def available_periods() -> list[str]:
    revenue = _read_csv("revenue_engine")
    if revenue.empty:
        return ["2026-01-01"]
    months = sorted(revenue["usage_date"].dt.to_period("M").astype(str).unique())
    return months
