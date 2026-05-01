"""Forecast and variance analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_forecast(assumptions_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate forecast revenue from fleet assumptions."""

    df = assumptions_df.copy()
    df["forecast_revenue"] = (
        df["fleet_count"]
        * df["hours_per_day"]
        * df["days"]
        * df["utilisation_pct"]
        * df["rate"]
    ).round().astype(int)
    df["forecast_hours"] = (
        df["fleet_count"] * df["hours_per_day"] * df["days"] * df["utilisation_pct"]
    )
    return df


def calculate_variance(forecast_df: pd.DataFrame, actual_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate revenue variance and split utilisation, rate and mix effects.

    Float fees are stripped from actual revenue before rate variance is calculated.
    """

    forecast = forecast_df.copy()
    if "forecast_revenue" not in forecast.columns:
        forecast = build_forecast(forecast)

    forecast_grouped = forecast.groupby("equipment_type", as_index=False).agg(
        forecast_revenue=("forecast_revenue", "sum"),
        forecast_hours=("forecast_hours", "sum"),
        forecast_rate=("rate", "mean"),
    )

    actual = actual_df.copy()
    actual["actual_hire_revenue"] = actual.get(
        "hire_revenue_cents",
        actual["total_revenue_cents"] - actual.get("float_applied_cents", 0),
    )
    actual_grouped = actual.groupby("equipment_type", as_index=False).agg(
        actual_revenue=("total_revenue_cents", "sum"),
        actual_hire_revenue=("actual_hire_revenue", "sum"),
        actual_hours=("billable_hours", "sum"),
        actual_rate=("rate_used_cents", "mean"),
    )

    df = forecast_grouped.merge(actual_grouped, on="equipment_type", how="outer").fillna(0)
    df["variance_amount"] = df["actual_revenue"] - df["forecast_revenue"]
    df["variance_pct"] = np.where(
        df["forecast_revenue"] == 0,
        0,
        (df["variance_amount"] / df["forecast_revenue"] * 100).round(2),
    )
    df["utilisation_variance"] = (
        (df["actual_hours"] - df["forecast_hours"]) * df["forecast_rate"]
    ).round().astype(int)
    df["rate_variance"] = (
        (df["actual_rate"] - df["forecast_rate"]) * df["actual_hours"]
    ).round().astype(int)
    df["mix_variance"] = (
        df["actual_hire_revenue"] - df["forecast_revenue"] - df["utilisation_variance"] - df["rate_variance"]
    ).round().astype(int)
    return df[
        [
            "equipment_type",
            "forecast_revenue",
            "actual_revenue",
            "variance_amount",
            "variance_pct",
            "utilisation_variance",
            "rate_variance",
            "mix_variance",
        ]
    ]
