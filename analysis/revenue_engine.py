"""Revenue calculations for wet-hire usage."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import pandas as pd

from .db import get_df


GST_RATE = 0.10


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "t", "1", "yes", "y"}
    return bool(value)


def _rate_lookup(rate_card: Any, equipment_type: str) -> dict[str, Any]:
    if isinstance(rate_card, pd.DataFrame):
        match = rate_card.loc[rate_card["equipment_type"] == equipment_type]
        if match.empty:
            raise KeyError(f"No rate-card row for {equipment_type}")
        return match.iloc[0].to_dict()
    row = rate_card[equipment_type]
    if isinstance(row, dict):
        return row
    return {
        "hourly_rate_cents": getattr(row, "hourly_rate_cents"),
        "float_fee_cents": getattr(row, "float_fee_cents"),
    }


def _override_lookup(job_rates: Any, job_id: str, equipment_type: str) -> int | None:
    if job_rates is None:
        return None
    if isinstance(job_rates, pd.DataFrame):
        if job_rates.empty:
            return None
        match = job_rates.loc[
            (job_rates["job_id"] == job_id) & (job_rates["equipment_type"] == equipment_type)
        ]
        if match.empty:
            return None
        return int(match.iloc[0]["override_rate_cents"])
    return job_rates.get((job_id, equipment_type))


def calculate_billable_hours(hours: float, rain_flag: bool, min_hours: float, rain_min: float) -> int:
    """Apply 8-hour minimum or 6-hour rain-off minimum."""

    minimum = rain_min if rain_flag else min_hours
    return int(math.ceil(max(float(hours), float(minimum))))


def calculate_float_fee(standard_float: int, total_term_hours: float) -> int:
    """Double the float fee when the total hire term is less than 16 hours."""

    return int(standard_float) * 2 if float(total_term_hours) < 16 else int(standard_float)


def calculate_revenue_row(usage_row: Any, rate_card: Any, job_rates: Any) -> dict[str, Any]:
    """Calculate one usage row using override-rate priority and contract rules."""

    job_id = _value(usage_row, "job_id")
    asset_id = _value(usage_row, "asset_id")
    equipment_type = _value(usage_row, "equipment_type")
    usage_id = _value(usage_row, "usage_id")
    usage_date = _value(usage_row, "usage_date")
    actual_hours = float(_value(usage_row, "hours_worked", _value(usage_row, "actual_hours", 0)))
    rain_flag = _bool(_value(usage_row, "rain_flag", False))
    float_required = _bool(_value(usage_row, "float_required", False))
    total_term_hours = float(_value(usage_row, "total_term_hours", actual_hours))

    rate_row = _rate_lookup(rate_card, equipment_type)
    standard_rate = int(rate_row["hourly_rate_cents"])
    standard_float = int(rate_row.get("float_fee_cents", 0))
    override_rate = _override_lookup(job_rates, job_id, equipment_type)
    rate_used = int(override_rate if override_rate is not None else standard_rate)
    rate_source = "Override" if override_rate is not None else "Rate card"

    billable_hours = calculate_billable_hours(actual_hours, rain_flag, 8, 6)
    hire_revenue = int(round(billable_hours * rate_used))
    float_applied = calculate_float_fee(standard_float, total_term_hours) if float_required else 0
    total_revenue = hire_revenue + float_applied
    gst_output = int(round(total_revenue * GST_RATE))

    return {
        "usage_id": usage_id,
        "job_id": job_id,
        "asset_id": asset_id,
        "equipment_type": equipment_type,
        "usage_date": usage_date,
        "actual_hours": actual_hours,
        "billable_hours": billable_hours,
        "rate_used_cents": rate_used,
        "rate_source": rate_source,
        "hire_revenue_cents": hire_revenue,
        "float_applied_cents": float_applied,
        "total_revenue_cents": total_revenue,
        "gst_output_cents": gst_output,
        "tax_code": "GST",
        "bas_g1_cents": total_revenue,
        "bas_1a_cents": gst_output,
    }


def run_revenue_engine(period: str | date | None = None) -> pd.DataFrame:
    """Run the revenue engine over usage_log rows from PostgreSQL."""

    where = ""
    params: dict[str, Any] = {}
    if period is not None:
        period_start = pd.to_datetime(period).date().replace(day=1)
        period_end = (pd.Timestamp(period_start) + pd.offsets.MonthEnd(1)).date()
        where = "WHERE u.usage_date BETWEEN :period_start AND :period_end"
        params = {"period_start": period_start, "period_end": period_end}

    usage = get_df(
        f"""
        WITH term_hours AS (
            SELECT job_id, asset_id, SUM(hours_worked) AS total_term_hours
            FROM usage_log
            GROUP BY job_id, asset_id
        )
        SELECT u.*, th.total_term_hours
        FROM usage_log u
        JOIN term_hours th
          ON th.job_id = u.job_id
         AND th.asset_id = u.asset_id
        {where}
        ORDER BY u.usage_date, u.job_id, u.asset_id
        """,
        params,
    )
    rate_card = get_df("SELECT equipment_type, hourly_rate_cents, float_fee_cents FROM rate_card")
    job_rates = get_df("SELECT job_id, equipment_type, override_rate_cents FROM job_rates")

    rows = [calculate_revenue_row(row, rate_card, job_rates) for row in usage.itertuples(index=False)]
    df = pd.DataFrame(rows)
    if not df.empty:
        df.insert(0, "revenue_id", [f"REV{i:05d}" for i in range(1, len(df) + 1)])
    return df


def detect_exceptions(revenue_df: pd.DataFrame) -> pd.DataFrame:
    """Return underbilling, overbilling and no-invoice exceptions from revenue output."""

    if revenue_df.empty:
        return pd.DataFrame(
            columns=["issue_type", "job_id", "asset_id", "earned_cents", "invoiced_cents", "variance_cents"]
        )

    earned = (
        revenue_df.groupby(["job_id", "asset_id"], as_index=False)["total_revenue_cents"]
        .sum()
        .rename(columns={"total_revenue_cents": "earned_cents"})
    )
    invoices = get_df(
        """
        SELECT job_id, asset_id, SUM(amount_ex_gst_cents)::INTEGER AS invoiced_cents,
               MAX(invoice_date) AS latest_invoice_date
        FROM invoice_myob
        GROUP BY job_id, asset_id
        """
    )
    merged = earned.merge(invoices, on=["job_id", "asset_id"], how="left")
    merged["invoiced_cents"] = merged["invoiced_cents"].fillna(0).astype(int)
    merged["variance_cents"] = merged["earned_cents"] - merged["invoiced_cents"]

    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        if row.invoiced_cents == 0:
            issue = "No invoice"
        elif row.variance_cents > 50_000:
            issue = "Underbilling"
        elif row.variance_cents < -50_000:
            issue = "Overbilling"
        else:
            continue
        rows.append(
            {
                "issue_type": issue,
                "job_id": row.job_id,
                "asset_id": row.asset_id,
                "earned_cents": int(row.earned_cents),
                "invoiced_cents": int(row.invoiced_cents),
                "variance_cents": int(row.variance_cents),
            }
        )
    return pd.DataFrame(rows)


def calculate_wip(earned_cents: int, invoiced_cents: int) -> int:
    """Calculate WIP as earned revenue less invoiced amount."""

    return int(earned_cents) - int(invoiced_cents)


def calculate_abn_withholding(gross_ex_gst_cents: int) -> int:
    """Calculate no-ABN withholding at 47% of gross ex-GST."""

    return int(round(int(gross_ex_gst_cents) * 0.47))
