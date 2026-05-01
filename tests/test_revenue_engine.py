import pandas as pd
import pytest

from analysis.compliance import assert_journal_balanced
from analysis.revenue_engine import (
    calculate_abn_withholding,
    calculate_billable_hours,
    calculate_float_fee,
    calculate_revenue_row,
    calculate_wip,
)


def test_rain_off_minimum_is_six_hours():
    assert calculate_billable_hours(6, rain_flag=True, min_hours=8, rain_min=6) == 6


def test_standard_minimum_is_eight_hours():
    assert calculate_billable_hours(7, rain_flag=False, min_hours=8, rain_min=6) == 8


def test_float_doubles_under_sixteen_total_hours():
    assert calculate_float_fee(50_000, total_term_hours=12) == 100_000


def test_float_does_not_double_at_eighteen_total_hours():
    assert calculate_float_fee(50_000, total_term_hours=18) == 50_000


def test_rate_override_takes_priority():
    usage_row = {
        "usage_id": "USE001",
        "job_id": "JOB001",
        "asset_id": "EX001",
        "equipment_type": "13T Excavator",
        "usage_date": "2026-01-05",
        "hours_worked": 8,
        "rain_flag": False,
        "float_required": False,
        "total_term_hours": 24,
    }
    rate_card = {"13T Excavator": {"hourly_rate_cents": 14_000, "float_fee_cents": 50_000}}
    job_rates = {("JOB001", "13T Excavator"): 13_000}

    result = calculate_revenue_row(usage_row, rate_card, job_rates)

    assert result["rate_used_cents"] == 13_000
    assert result["rate_source"] == "Override"


def test_wip_positive():
    assert calculate_wip(earned_cents=178_000, invoiced_cents=104_000) == 74_000


def test_abn_withholding():
    assert calculate_abn_withholding(120_000) == 56_400


def test_journal_balance_passes_when_dr_equals_cr():
    journal = pd.DataFrame(
        [
            {"dr": 100_000, "cr": 0},
            {"dr": 0, "cr": 100_000},
        ]
    )

    assert_journal_balanced(journal)


def test_journal_balance_raises_when_unbalanced():
    journal = pd.DataFrame(
        [
            {"dr": 100_000, "cr": 0},
            {"dr": 0, "cr": 99_999},
        ]
    )

    with pytest.raises(ValueError):
        assert_journal_balanced(journal)
