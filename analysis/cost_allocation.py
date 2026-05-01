"""Direct cost allocation and profitability analysis."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .db import get_df, get_scalar


def _period_filter(alias: str, period: str | date | None, date_col: str) -> tuple[str, dict[str, Any]]:
    if period is None:
        return "", {}
    start = pd.to_datetime(period).date().replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(1)).date()
    return f" AND {alias}.{date_col} BETWEEN :period_start AND :period_end", {
        "period_start": start,
        "period_end": end,
    }


def allocate_direct_costs(job_id: str, asset_id: str) -> pd.DataFrame:
    """Return direct costs for one job and asset grouped by category."""

    return get_df(
        """
        SELECT
            cost_category,
            SUM(amount_cents)::INTEGER AS amount_cents,
            SUM(gst_input_cents)::INTEGER AS gst_input_cents
        FROM costs
        WHERE job_id = :job_id
          AND asset_id = :asset_id
        GROUP BY cost_category
        ORDER BY cost_category
        """,
        {"job_id": job_id, "asset_id": asset_id},
    )


def allocate_maintenance_per_hour(asset_id: str, period: str | date) -> float:
    """Calculate maintenance cents per actual hour for an asset and month."""

    start = pd.to_datetime(period).date().replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(1)).date()
    value = get_scalar(
        """
        WITH hours AS (
            SELECT SUM(hours_worked) AS actual_hours
            FROM usage_log
            WHERE asset_id = :asset_id
              AND usage_date BETWEEN :period_start AND :period_end
        ),
        maintenance AS (
            SELECT SUM(amount_cents) AS maintenance_cents
            FROM costs
            WHERE asset_id = :asset_id
              AND cost_category = 'Maintenance'
              AND cost_date BETWEEN :period_start AND :period_end
        )
        SELECT COALESCE(maintenance_cents, 0)::NUMERIC / NULLIF(actual_hours, 0)
        FROM hours, maintenance
        """,
        {"asset_id": asset_id, "period_start": start, "period_end": end},
    )
    return float(value or 0)


def allocate_transport_per_job(job_id: str) -> float:
    """Calculate transport and float cost for one job."""

    value = get_scalar(
        """
        SELECT COALESCE(SUM(amount_cents), 0)
        FROM costs
        WHERE job_id = :job_id
          AND cost_category = 'Transport/float'
        """,
        {"job_id": job_id},
    )
    return float(value or 0)


def build_job_profit(period: str | date | None = None) -> pd.DataFrame:
    """Build job-level profit columns for dashboard and export."""

    revenue_filter, params = _period_filter("re", period, "usage_date")
    cost_filter, _ = _period_filter("c", period, "cost_date")
    return get_df(
        f"""
        WITH revenue AS (
            SELECT job_id, SUM(total_revenue_cents)::INTEGER AS revenue
            FROM revenue_engine re
            WHERE 1 = 1 {revenue_filter}
            GROUP BY job_id
        ),
        costs_by_job AS (
            SELECT
                job_id,
                SUM(CASE WHEN cost_category = 'Fuel' THEN amount_cents ELSE 0 END)::INTEGER AS fuel_cost,
                SUM(CASE WHEN cost_category = 'Labour' THEN amount_cents ELSE 0 END)::INTEGER AS labour_cost,
                SUM(CASE WHEN cost_category = 'Maintenance' THEN amount_cents ELSE 0 END)::INTEGER AS maintenance_cost,
                SUM(CASE WHEN cost_category = 'Transport/float' THEN amount_cents ELSE 0 END)::INTEGER AS transport_cost,
                SUM(amount_cents)::INTEGER AS total_cost
            FROM costs c
            WHERE 1 = 1 {cost_filter}
            GROUP BY job_id
        )
        SELECT
            jm.job_id,
            jm.customer_name AS customer,
            COALESCE(r.revenue, 0) AS revenue,
            COALESCE(c.fuel_cost, 0) AS fuel_cost,
            COALESCE(c.labour_cost, 0) AS labour_cost,
            COALESCE(c.maintenance_cost, 0) AS maintenance_cost,
            COALESCE(c.transport_cost, 0) AS transport_cost,
            COALESCE(c.total_cost, 0) AS total_cost,
            COALESCE(r.revenue, 0) - COALESCE(c.total_cost, 0) AS profit,
            CASE
                WHEN COALESCE(r.revenue, 0) = 0 THEN 0
                ELSE ROUND((COALESCE(r.revenue, 0) - COALESCE(c.total_cost, 0))::NUMERIC / r.revenue * 100, 2)
            END AS margin_pct
        FROM job_master jm
        LEFT JOIN revenue r ON r.job_id = jm.job_id
        LEFT JOIN costs_by_job c ON c.job_id = jm.job_id
        ORDER BY margin_pct ASC
        """,
        params,
    )


def build_asset_profit(period: str | date | None = None) -> pd.DataFrame:
    """Build asset-level profit columns for dashboard and export."""

    revenue_filter, params = _period_filter("re", period, "usage_date")
    cost_filter, _ = _period_filter("c", period, "cost_date")
    return get_df(
        f"""
        WITH revenue AS (
            SELECT asset_id, SUM(total_revenue_cents)::INTEGER AS revenue
            FROM revenue_engine re
            WHERE 1 = 1 {revenue_filter}
            GROUP BY asset_id
        ),
        costs_by_asset AS (
            SELECT
                asset_id,
                SUM(CASE WHEN cost_category = 'Fuel' THEN amount_cents ELSE 0 END)::INTEGER AS fuel_cost,
                SUM(CASE WHEN cost_category = 'Labour' THEN amount_cents ELSE 0 END)::INTEGER AS labour_cost,
                SUM(CASE WHEN cost_category = 'Maintenance' THEN amount_cents ELSE 0 END)::INTEGER AS maintenance_cost,
                SUM(CASE WHEN cost_category = 'Transport/float' THEN amount_cents ELSE 0 END)::INTEGER AS transport_cost,
                SUM(amount_cents)::INTEGER AS total_cost
            FROM costs c
            WHERE asset_id IS NOT NULL {cost_filter}
            GROUP BY asset_id
        )
        SELECT
            fr.asset_id,
            fr.equipment_type,
            COALESCE(r.revenue, 0) AS revenue,
            COALESCE(c.fuel_cost, 0) AS fuel_cost,
            COALESCE(c.labour_cost, 0) AS labour_cost,
            COALESCE(c.maintenance_cost, 0) AS maintenance_cost,
            COALESCE(c.transport_cost, 0) AS transport_cost,
            COALESCE(c.total_cost, 0) AS total_cost,
            COALESCE(r.revenue, 0) - COALESCE(c.total_cost, 0) AS profit,
            CASE
                WHEN COALESCE(r.revenue, 0) = 0 THEN 0
                ELSE ROUND((COALESCE(r.revenue, 0) - COALESCE(c.total_cost, 0))::NUMERIC / r.revenue * 100, 2)
            END AS margin_pct
        FROM fleet_register fr
        LEFT JOIN revenue r ON r.asset_id = fr.asset_id
        LEFT JOIN costs_by_asset c ON c.asset_id = fr.asset_id
        ORDER BY margin_pct ASC
        """,
        params,
    )
