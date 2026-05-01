"""Compliance, reconciliation and journal-pack analysis."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .db import get_df
from .revenue_engine import calculate_abn_withholding


def _period_bounds(period: str | date) -> tuple[date, date]:
    start = pd.to_datetime(period).date().replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(1)).date()
    return start, end


def assert_journal_balanced(journal_df: pd.DataFrame) -> None:
    """Raise ValueError when journal debits and credits do not balance."""

    dr = int(journal_df["dr"].sum()) if "dr" in journal_df else 0
    cr = int(journal_df["cr"].sum()) if "cr" in journal_df else 0
    if dr != cr:
        raise ValueError(f"Journal pack is not balanced: DR {dr} != CR {cr}")


def build_bas_check(period: str | date) -> pd.DataFrame:
    """Build BAS fields for the period; W4 is excluded from Net GST."""

    start, end = _period_bounds(period)
    revenue = get_df(
        """
        SELECT
            COALESCE(SUM(bas_g1_cents), 0)::INTEGER AS g1,
            COALESCE(SUM(bas_1a_cents), 0)::INTEGER AS one_a
        FROM revenue_engine
        WHERE usage_date BETWEEN :start AND :end
        """,
        {"start": start, "end": end},
    ).iloc[0]
    costs = get_df(
        """
        SELECT
            COALESCE(SUM(bas_g11_cents), 0)::INTEGER AS g11,
            COALESCE(SUM(bas_1b_cents), 0)::INTEGER AS one_b
        FROM costs
        WHERE cost_date BETWEEN :start AND :end
        """,
        {"start": start, "end": end},
    ).iloc[0]
    w4 = get_df(
        """
        SELECT COALESCE(SUM(p.withholding_cents), 0)::INTEGER AS w4
        FROM payg_withholding p
        JOIN costs c ON c.cost_id = p.cost_id
        WHERE c.cost_date BETWEEN :start AND :end
        """,
        {"start": start, "end": end},
    ).iloc[0]["w4"]

    one_a = int(revenue["one_a"])
    one_b = int(costs["one_b"])
    return pd.DataFrame(
        [
            {
                "period": start,
                "G1": int(revenue["g1"]),
                "G2": 0,
                "G3": 0,
                "G10": 0,
                "G11": int(costs["g11"]),
                "1A": one_a,
                "1B": one_b,
                "W4": int(w4),
                "Net GST": one_a - one_b,
            }
        ]
    )


def build_payg_withholding(period: str | date) -> pd.DataFrame:
    """Return no-ABN PAYG withholding rows for the period."""

    start, end = _period_bounds(period)
    return get_df(
        """
        SELECT
            p.payg_withholding_id,
            p.job_id,
            p.cost_id,
            p.supplier_name,
            p.gross_ex_gst_cents,
            p.withholding_rate,
            p.withholding_cents,
            p.liability_account,
            p.bas_field,
            FALSE AS included_in_net_gst
        FROM payg_withholding p
        JOIN costs c ON c.cost_id = p.cost_id
        WHERE c.cost_date BETWEEN :start AND :end
        ORDER BY p.job_id, p.cost_id
        """,
        {"start": start, "end": end},
    )


def build_myob_recon(period: str | date) -> pd.DataFrame:
    """Compare model Revenue, Cost, WIP and Profit to seeded MYOB extract where available."""

    start, end = _period_bounds(period)
    model = get_df(
        """
        WITH revenue AS (
            SELECT COALESCE(SUM(total_revenue_cents), 0)::INTEGER AS amount
            FROM revenue_engine
            WHERE usage_date BETWEEN :start AND :end
        ),
        cost AS (
            SELECT COALESCE(SUM(amount_cents), 0)::INTEGER AS amount
            FROM costs
            WHERE cost_date BETWEEN :start AND :end
        ),
        wip AS (
            SELECT COALESCE(SUM(wip_cents), 0)::INTEGER AS amount
            FROM wip_summary
        )
        SELECT 'Revenue' AS metric, amount FROM revenue
        UNION ALL SELECT 'Cost', amount FROM cost
        UNION ALL SELECT 'WIP', amount FROM wip
        UNION ALL SELECT 'Profit', (SELECT amount FROM revenue) - (SELECT amount FROM cost)
        """,
        {"start": start, "end": end},
    )
    myob = get_df(
        """
        SELECT
            CASE
                WHEN account_name ILIKE '%Revenue%' THEN 'Revenue'
                WHEN account_name ILIKE '%Expense%' THEN 'Cost'
                ELSE account_name
            END AS metric,
            SUM(credit_cents - debit_cents)::INTEGER AS myob_amount
        FROM myob_gl_extract
        WHERE period_start = :start
        GROUP BY 1
        """,
        {"start": start},
    )
    df = model.merge(myob, on="metric", how="left").fillna({"myob_amount": 0})
    df["variance_cents"] = df["amount"].astype(int) - df["myob_amount"].astype(int)
    df["status"] = df["variance_cents"].abs().le(100).map({True: "OK", False: "CHECK"})
    return df.rename(columns={"amount": "model_amount"})


def build_journal_pack(period: str | date) -> pd.DataFrame:
    """Build JE001-JE004 for a period and raise if debits and credits do not balance."""

    start, end = _period_bounds(period)
    rows: list[dict[str, Any]] = []

    wip = int(
        get_df("SELECT COALESCE(SUM(GREATEST(wip_cents, 0)), 0)::INTEGER AS amount FROM wip_summary").iloc[0][
            "amount"
        ]
    )
    cost = int(
        get_df(
            "SELECT COALESCE(SUM(amount_cents), 0)::INTEGER AS amount FROM costs WHERE cost_date BETWEEN :start AND :end",
            {"start": start, "end": end},
        ).iloc[0]["amount"]
    )
    asset_count = int(get_df("SELECT COUNT(*)::INTEGER AS count FROM fleet_register").iloc[0]["count"])
    depreciation = asset_count * 750_000
    payg = int(
        get_df(
            """
            SELECT COALESCE(SUM(p.withholding_cents), 0)::INTEGER AS amount
            FROM payg_withholding p
            JOIN costs c ON c.cost_id = p.cost_id
            WHERE c.cost_date BETWEEN :start AND :end
            """,
            {"start": start, "end": end},
        ).iloc[0]["amount"]
    )

    def add(journal_id: str, name: str, account: str, dr: int, cr: int) -> None:
        rows.append(
            {
                "journal_id": journal_id,
                "period": start,
                "journal_name": name,
                "account_name": account,
                "dr": int(dr),
                "cr": int(cr),
            }
        )

    add("JE001", "WIP Accrual", "Unbilled Revenue", wip, 0)
    add("JE001", "WIP Accrual", "Hire Revenue", 0, wip)
    add("JE002", "Cost Accrual", "Operating Expense", cost, 0)
    add("JE002", "Cost Accrual", "Accrued Expenses", 0, cost)
    add("JE003", "Depreciation", "Depreciation Expense", depreciation, 0)
    add("JE003", "Depreciation", "Accumulated Depreciation", 0, depreciation)
    add("JE004", "PAYG No-ABN", "Trade Payables", payg, 0)
    add("JE004", "PAYG No-ABN", "PAYG Withholding Payable", 0, payg)

    df = pd.DataFrame(rows)
    assert_journal_balanced(df)
    return df


def build_payroll_compliance(period: str | date) -> pd.DataFrame:
    """Compare expected super, payroll tax and CoINVEST against recorded payroll rows."""

    start, _ = _period_bounds(period)
    return get_df(
        """
        WITH cfg AS (
            SELECT
                MAX(CASE WHEN config_key = 'super_guarantee_rate' THEN config_value END) AS super_rate,
                MAX(CASE WHEN config_key = 'vic_payroll_tax_rate' THEN config_value END) AS payroll_tax_rate,
                MAX(CASE WHEN config_key = 'vic_payroll_tax_monthly_threshold' THEN config_value END) * 100 AS threshold_cents,
                MAX(CASE WHEN config_key = 'coinvest_rate' THEN config_value END) AS coinvest_rate
            FROM payroll_config
        ),
        total_wages AS (
            SELECT SUM(gross_wages_cents)::INTEGER AS gross_wages_cents
            FROM payroll_monthly
            WHERE month_start = :start
        )
        SELECT
            pm.month_start AS period,
            pm.pay_group,
            pm.gross_wages_cents,
            ROUND(pm.gross_wages_cents * cfg.super_rate)::INTEGER AS expected_super_cents,
            pm.super_guarantee_cents AS myob_super_cents,
            (pm.super_guarantee_cents - ROUND(pm.gross_wages_cents * cfg.super_rate))::INTEGER AS super_variance_cents,
            ROUND(
                GREATEST(tw.gross_wages_cents - cfg.threshold_cents, 0)
                * cfg.payroll_tax_rate
                * (pm.gross_wages_cents::NUMERIC / NULLIF(tw.gross_wages_cents, 0))
            )::INTEGER AS expected_payroll_tax_cents,
            pm.payroll_tax_cents AS myob_payroll_tax_cents,
            pm.payroll_tax_cents - ROUND(
                GREATEST(tw.gross_wages_cents - cfg.threshold_cents, 0)
                * cfg.payroll_tax_rate
                * (pm.gross_wages_cents::NUMERIC / NULLIF(tw.gross_wages_cents, 0))
            )::INTEGER AS payroll_tax_variance_cents,
            ROUND(pm.gross_wages_cents * cfg.coinvest_rate)::INTEGER AS expected_coinvest_cents,
            pm.coinvest_cents AS myob_coinvest_cents,
            pm.coinvest_cents - ROUND(pm.gross_wages_cents * cfg.coinvest_rate)::INTEGER AS coinvest_variance_cents
        FROM payroll_monthly pm
        CROSS JOIN cfg
        CROSS JOIN total_wages tw
        WHERE pm.month_start = :start
        ORDER BY pm.pay_group
        """,
        {"start": start},
    )


def build_fuel_tax_credit(period: str | date) -> pd.DataFrame:
    """Return Fuel Tax Credit estimates for the period."""

    start, _ = _period_bounds(period)
    return get_df(
        """
        SELECT
            ftc.month_start AS period,
            ftc.asset_id,
            fr.equipment_type,
            ftc.fuel_cost_cents,
            ftc.litres,
            ftc.ato_eligible_rate_cents_per_litre,
            ftc.fuel_tax_credit_cents,
            ftc.note
        FROM fuel_tax_credit ftc
        JOIN fleet_register fr ON fr.asset_id = ftc.asset_id
        WHERE ftc.month_start = :start
        ORDER BY ftc.asset_id
        """,
        {"start": start},
    )


__all__ = [
    "assert_journal_balanced",
    "build_bas_check",
    "build_payg_withholding",
    "build_myob_recon",
    "build_journal_pack",
    "build_payroll_compliance",
    "build_fuel_tax_credit",
    "calculate_abn_withholding",
]
