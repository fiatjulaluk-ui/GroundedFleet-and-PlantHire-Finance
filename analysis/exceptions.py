"""Unified exception scanning across finance-control modules."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .compliance import build_journal_pack, build_payroll_compliance
from .db import get_df


def _bounds(period: str | date | None) -> tuple[str, dict[str, Any]]:
    if period is None:
        return "", {}
    start = pd.to_datetime(period).date().replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(1)).date()
    return " AND usage_date BETWEEN :start AND :end", {"start": start, "end": end}


def _exception(
    issue_type: str,
    source: str,
    description: str,
    severity: str,
    suggested_action: str,
    period: Any,
    status: str = "Open",
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "source": source,
        "description": description,
        "severity": severity,
        "suggested_action": suggested_action,
        "status": status,
        "period": period,
    }


def scan_exceptions(period: str | date | None = None) -> pd.DataFrame:
    """Scan all modules and return a unified exception log."""

    rows: list[dict[str, Any]] = []
    revenue_filter, params = _bounds(period)
    period_label = pd.to_datetime(period).date().replace(day=1) if period is not None else None

    billing = get_df(
        f"""
        WITH earned AS (
            SELECT job_id, asset_id, MAX(usage_date) AS last_usage_date,
                   SUM(total_revenue_cents)::INTEGER AS earned_cents
            FROM revenue_engine
            WHERE 1 = 1 {revenue_filter}
            GROUP BY job_id, asset_id
        ),
        invoiced AS (
            SELECT job_id, asset_id, SUM(amount_ex_gst_cents)::INTEGER AS invoiced_cents
            FROM invoice_myob
            GROUP BY job_id, asset_id
        )
        SELECT e.*, COALESCE(i.invoiced_cents, 0) AS invoiced_cents,
               e.earned_cents - COALESCE(i.invoiced_cents, 0) AS variance_cents
        FROM earned e
        LEFT JOIN invoiced i ON i.job_id = e.job_id AND i.asset_id = e.asset_id
        """,
        params,
    )
    for item in billing.itertuples(index=False):
        desc = f"{item.job_id}/{item.asset_id}: earned {item.earned_cents}, invoiced {item.invoiced_cents}"
        if item.invoiced_cents == 0 and pd.Timestamp(date.today()).date() > item.last_usage_date + pd.Timedelta(days=14):
            rows.append(
                _exception("No invoice", "revenue_engine", desc, "HIGH", "Create or investigate missing MYOB invoice", period_label)
            )
        elif item.variance_cents > 50_000:
            rows.append(
                _exception("Underbilling", "wip_summary", desc, "HIGH", "Review rate, float and invoice amount", period_label)
            )
        elif item.variance_cents < -50_000:
            rows.append(
                _exception("Overbilling", "wip_summary", desc, "HIGH", "Review credit or revenue correction", period_label)
            )

    rows.extend(
        _exception(
            "No ABN withholding",
            "payg_withholding",
            f"{row.cost_id}: ABN-coded cost has no W4 withholding entry",
            "HIGH",
            "Create PAYG withholding liability and BAS W4 entry",
            period_label,
        )
        for row in get_df(
            """
            SELECT c.cost_id
            FROM costs c
            LEFT JOIN payg_withholding p ON p.cost_id = c.cost_id
            WHERE c.tax_code = 'ABN'
              AND p.cost_id IS NULL
            """
        ).itertuples(index=False)
    )

    rows.extend(
        _exception(
            "Orphan cost",
            "costs",
            f"{row.cost_id}: cost references missing job_id {row.job_id}",
            "HIGH",
            "Assign cost to a valid job or remove from model load",
            period_label,
        )
        for row in get_df(
            """
            SELECT c.cost_id, c.job_id
            FROM costs c
            LEFT JOIN job_master jm ON jm.job_id = c.job_id
            WHERE jm.job_id IS NULL
            """
        ).itertuples(index=False)
    )

    check_period = period or date.today().replace(day=1)
    try:
        build_journal_pack(check_period)
    except ValueError as exc:
        rows.append(
            _exception(
                "Journal imbalance",
                "journal_pack",
                str(exc),
                "HIGH",
                "Inspect JE001-JE004 debit and credit construction",
                period_label,
            )
        )

    try:
        payroll = build_payroll_compliance(check_period)
        for item in payroll.itertuples(index=False):
            if abs(int(item.super_variance_cents)) > 5_000 or abs(int(item.payroll_tax_variance_cents)) > 5_000:
                rows.append(
                    _exception(
                        "Payroll variance",
                        "payroll_compliance",
                        f"{item.pay_group}: super variance {item.super_variance_cents}, payroll tax variance {item.payroll_tax_variance_cents}",
                        "MEDIUM",
                        "Reconcile payroll report to expected super and payroll tax",
                        item.period,
                    )
                )
    except Exception as exc:
        rows.append(
            _exception(
                "Payroll variance",
                "payroll_compliance",
                f"Payroll scan could not run: {exc}",
                "LOW",
                "Check payroll seed data and configuration",
                period_label,
            )
        )

    ftc_stale = get_df(
        """
        SELECT asset_id, month_start, updated_at
        FROM fuel_tax_credit
        WHERE updated_at < now() - INTERVAL '180 days'
        """
    )
    for item in ftc_stale.itertuples(index=False):
        rows.append(
            _exception(
                "FTC rate stale",
                "fuel_tax_credit",
                f"{item.asset_id}/{item.month_start}: FTC rate row is older than 180 days",
                "MEDIUM",
                "Update fuel tax credit rate from ATO guidance",
                item.month_start,
            )
        )

    return pd.DataFrame(
        rows,
        columns=[
            "issue_type",
            "source",
            "description",
            "severity",
            "suggested_action",
            "status",
            "period",
        ],
    )
