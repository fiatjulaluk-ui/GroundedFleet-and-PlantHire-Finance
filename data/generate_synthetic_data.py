"""Generate synthetic finance control data for Grounded Fleet & Plant Hire.

Outputs one CSV per generated table into data/csv/.
Money is stored as integer cents throughout.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from faker import Faker


SEED = 20260501
START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 6, 30)
GST_RATE = 0.10
ABN_WITHHOLDING_RATE = 0.47
DIESEL_PRICE_CENTS_PER_LITRE = 210
FUEL_TAX_CREDIT_CENTS_PER_LITRE = 0.20

ROOT_DIR = Path(__file__).resolve().parent
CSV_DIR = ROOT_DIR / "csv"

EMPTY_TABLE_HEADERS = {
    "exception_log": [
        "exception_id",
        "exception_type",
        "job_id",
        "asset_id",
        "amount_cents",
        "message",
    ],
}

fake = Faker("en_AU")
Faker.seed(SEED)
random.seed(SEED)
np.random.seed(SEED)


@dataclass(frozen=True)
class RateCardItem:
    equipment_type: str
    hourly_rate_cents: int
    float_fee_cents: int


RATE_CARD: list[RateCardItem] = [
    RateCardItem("13T Excavator", 14_000, 50_000),
    RateCardItem("20T Excavator", 15_000, 60_000),
    RateCardItem("26T Excavator", 15_000, 65_000),
    RateCardItem("35T Excavator", 17_000, 70_000),
    RateCardItem("50T Excavator", 21_000, 90_000),
    RateCardItem("Dump Truck 30T", 18_500, 70_000),
    RateCardItem("Compactor 815F", 23_000, 80_000),
    RateCardItem("Bobcat+8T Tipper", 14_500, 50_000),
    RateCardItem("3T Excavator + 8T Tip", 14_500, 50_000),
    RateCardItem("Loader 3m", 16_000, 65_000),
    RateCardItem("Loader 4m", 18_000, 70_000),
    RateCardItem("Dozer D6", 23_000, 90_000),
    RateCardItem("Grader 12M", 19_000, 80_000),
    RateCardItem("Truck Tandem", 15_500, 60_000),
    RateCardItem("Truck and Dog", 25_000, 85_000),
    RateCardItem("Truck Float", 25_000, 100_000),
    RateCardItem("GPS add-on", 3_500, 0),
    RateCardItem("Hammer 25T", 5_000, 0),
    RateCardItem("Hammer 35T", 6_000, 0),
    RateCardItem("Hammer 50T", 7_000, 0),
]

FLEET_ASSETS = [
    ("EX001", "13T Excavator"),
    ("EX002", "20T Excavator"),
    ("EX003", "26T Excavator"),
    ("EX004", "35T Excavator"),
    ("EX005", "50T Excavator"),
    ("DT001", "Dump Truck 30T"),
    ("CP001", "Compactor 815F"),
    ("BC001", "Bobcat+8T Tipper"),
    ("LD001", "Loader 3m"),
    ("LD002", "Loader 4m"),
    ("DZ001", "Dozer D6"),
    ("GR001", "Grader 12M"),
]

CUSTOMERS = [
    "ABC Civil",
    "XYZ Earthworks",
    "Metro Projects",
    "Southside Civil",
    "Broadmeadows Builders",
    "Cranbourne Civil",
    "Pakenham Earthworks",
    "Hume Group",
]

SITES = [
    "Melbourne North",
    "Geelong",
    "Epping",
    "Dandenong",
    "Broadmeadows",
    "Cranbourne",
    "Pakenham",
    "Campbellfield",
]

OPERATORS = [
    "Noah Williams",
    "Jack Smith",
    "William Jones",
    "Thomas Brown",
    "Lucas Wilson",
    "Oliver Taylor",
    "Henry Johnson",
    "Lachlan Martin",
]


def cents_from_dollars(amount: float) -> int:
    return int(round(amount * 100))


def round_cents(amount: float) -> int:
    return int(round(amount))


def daterange(start: date, end: date) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def working_days(start: date, end: date) -> list[date]:
    return [day for day in daterange(start, end) if day.weekday() < 6]


def month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def csv_write(table_name: str, rows: list[dict]) -> None:
    path = CSV_DIR / f"{table_name}.csv"
    if not rows:
        headers = EMPTY_TABLE_HEADERS.get(table_name, [])
        with path.open("w", newline="", encoding="utf-8") as handle:
            if headers:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_rate_card() -> list[dict]:
    return [
        {
            "rate_card_id": f"RC{idx:03d}",
            "equipment_type": item.equipment_type,
            "hourly_rate_cents": item.hourly_rate_cents,
            "float_fee_cents": item.float_fee_cents,
            "effective_from": "2023-05-01",
            "effective_to": "",
            "source_note": "May 2023 source of truth; update quarterly or yearly as approved",
        }
        for idx, item in enumerate(RATE_CARD, start=1)
    ]


def generate_fleet_register() -> list[dict]:
    status_choices = ["Active", "In Workshop", "On Hire"]
    status_weights = [0.80, 0.10, 0.10]
    fleet_rows = []
    for asset_id, equipment_type in FLEET_ASSETS:
        fleet_rows.append(
            {
                "asset_id": asset_id,
                "equipment_type": equipment_type,
                "serial_number": fake.bothify(text="GF-####-??").upper(),
                "purchase_date": fake.date_between(
                    start_date=date(2018, 1, 1), end_date=date(2025, 12, 31)
                ).isoformat(),
                "status": random.choices(status_choices, weights=status_weights, k=1)[0],
                "home_depot": "Campbellfield",
            }
        )
    return fleet_rows


def generate_job_master() -> list[dict]:
    jobs = []
    latest_start = END_DATE - timedelta(days=21)
    for idx in range(1, 41):
        duration_days = random.randint(3, 21)
        start = fake.date_between(start_date=START_DATE, end_date=latest_start)
        end = min(start + timedelta(days=duration_days - 1), END_DATE)
        status = random.choices(
            ["Open", "Completed", "Invoiced"], weights=[0.20, 0.45, 0.35], k=1
        )[0]
        jobs.append(
            {
                "job_id": f"JOB{idx:04d}",
                "customer_name": random.choice(CUSTOMERS),
                "site_name": random.choice(SITES),
                "site_address": fake.street_address() + ", " + fake.city() + " VIC",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "duration_days": duration_days,
                "status": status,
                "purchase_order": fake.bothify(text="PO-2026-####").upper(),
            }
        )
    return jobs


def generate_usage_log(jobs: list[dict]) -> list[dict]:
    usage_rows = []
    usage_id = 1
    asset_operator = {
        asset_id: OPERATORS[idx % len(OPERATORS)]
        for idx, (asset_id, _equipment_type) in enumerate(FLEET_ASSETS)
    }

    for job in jobs:
        start = date.fromisoformat(job["start_date"])
        end = date.fromisoformat(job["end_date"])
        job_days = working_days(start, end)
        if not job_days:
            continue

        selected_assets = random.sample(FLEET_ASSETS, k=random.randint(2, 5))
        for asset_id, equipment_type in selected_assets:
            for work_day in job_days:
                hours = float(np.clip(np.random.normal(loc=9.0, scale=1.35), 6.0, 12.0))
                hours = round(hours * 2) / 2
                usage_rows.append(
                    {
                        "usage_id": f"USE{usage_id:05d}",
                        "job_id": job["job_id"],
                        "asset_id": asset_id,
                        "equipment_type": equipment_type,
                        "usage_date": work_day.isoformat(),
                        "site_name": job["site_name"],
                        "hours_worked": f"{hours:.1f}",
                        "rain_flag": random.random() < 0.12,
                        "float_required": False,
                        "operator_name": asset_operator[asset_id],
                    }
                )
                usage_id += 1

    previous_site_by_asset: dict[str, str] = {}
    for row in sorted(usage_rows, key=lambda item: (item["asset_id"], item["usage_date"], item["job_id"])):
        asset_id = row["asset_id"]
        prior_site = previous_site_by_asset.get(asset_id)
        if prior_site is None or prior_site != row["site_name"]:
            row["float_required"] = True
        previous_site_by_asset[asset_id] = row["site_name"]

    return sorted(usage_rows, key=lambda item: (item["usage_date"], item["job_id"], item["asset_id"]))


def generate_job_rates(usage_rows: list[dict], rate_by_type: dict[str, RateCardItem]) -> list[dict]:
    combos = sorted({(row["job_id"], row["equipment_type"]) for row in usage_rows})
    override_count = round(len(combos) * 0.15)
    selected = set(random.sample(combos, k=override_count))

    job_rates = []
    for idx, (job_id, equipment_type) in enumerate(sorted(selected), start=1):
        standard_rate = rate_by_type[equipment_type].hourly_rate_cents
        multiplier = random.uniform(0.85, 1.15)
        override_rate = round_cents(standard_rate * multiplier)
        job_rates.append(
            {
                "job_rate_id": f"JR{idx:04d}",
                "job_id": job_id,
                "equipment_type": equipment_type,
                "override_rate_cents": override_rate,
                "standard_rate_cents": standard_rate,
                "override_reason": random.choice(
                    ["Customer discount", "Premium machine", "Negotiated package"]
                ),
            }
        )
    return job_rates


def generate_revenue_engine(
    usage_rows: list[dict],
    job_rates: list[dict],
    rate_by_type: dict[str, RateCardItem],
) -> list[dict]:
    override_by_combo = {
        (row["job_id"], row["equipment_type"]): row["override_rate_cents"]
        for row in job_rates
    }
    total_term_hours = defaultdict(float)
    for row in usage_rows:
        total_term_hours[(row["job_id"], row["asset_id"])] += float(row["hours_worked"])

    revenue_rows = []
    for row in usage_rows:
        rate_item = rate_by_type[row["equipment_type"]]
        rate_used = override_by_combo.get(
            (row["job_id"], row["equipment_type"]), rate_item.hourly_rate_cents
        )
        actual_hours = float(row["hours_worked"])
        min_hours = 8.0
        rain_min_hours = 6.0
        billable_hours = max(actual_hours, rain_min_hours if row["rain_flag"] else min_hours)
        hire_revenue = round_cents(billable_hours * rate_used)
        float_fee = 0
        if row["float_required"]:
            float_fee = rate_item.float_fee_cents
            if total_term_hours[(row["job_id"], row["asset_id"])] < 16:
                float_fee *= 2
        total_revenue = hire_revenue + float_fee
        gst_output = round_cents(total_revenue * GST_RATE)

        revenue_rows.append(
            {
                "revenue_id": f"REV{len(revenue_rows) + 1:05d}",
                "usage_id": row["usage_id"],
                "job_id": row["job_id"],
                "asset_id": row["asset_id"],
                "equipment_type": row["equipment_type"],
                "usage_date": row["usage_date"],
                "actual_hours": f"{actual_hours:.1f}",
                "billable_hours": f"{billable_hours:.1f}",
                "rate_used_cents": rate_used,
                "rate_source": "Override" if (row["job_id"], row["equipment_type"]) in override_by_combo else "Rate card",
                "hire_revenue_cents": hire_revenue,
                "float_applied_cents": float_fee,
                "total_revenue_cents": total_revenue,
                "gst_output_cents": gst_output,
                "tax_code": "GST",
                "bas_g1_cents": total_revenue,
                "bas_1a_cents": gst_output,
            }
        )
    return revenue_rows


def equipment_size_factor(equipment_type: str) -> float:
    if any(token in equipment_type for token in ["50T", "Dozer", "Compactor"]):
        return 1.00
    if any(token in equipment_type for token in ["35T", "30T", "Grader", "Loader 4m"]):
        return 0.78
    if any(token in equipment_type for token in ["20T", "26T", "Loader 3m"]):
        return 0.62
    return 0.45


def generate_costs(
    usage_rows: list[dict],
    jobs: list[dict],
) -> tuple[list[dict], list[dict]]:
    costs = []
    payg_rows = []
    cost_id = 1

    def add_cost(
        *,
        usage_id: str,
        job_id: str,
        asset_id: str,
        cost_date: str,
        cost_category: str,
        amount_cents: int,
        tax_code: str,
        supplier_name: str,
        gst_creditable: bool,
        withholding_cents: int = 0,
    ) -> None:
        nonlocal cost_id
        gst_input = round_cents(amount_cents * GST_RATE) if gst_creditable else 0
        costs.append(
            {
                "cost_id": f"COST{cost_id:06d}",
                "usage_id": usage_id,
                "job_id": job_id,
                "asset_id": asset_id,
                "cost_date": cost_date,
                "cost_category": cost_category,
                "amount_cents": amount_cents,
                "gst_input_cents": gst_input,
                "tax_code": tax_code,
                "bas_g11_cents": amount_cents if gst_creditable else 0,
                "bas_1b_cents": gst_input,
                "supplier_name": supplier_name,
                "withholding_cents": withholding_cents,
            }
        )
        cost_id += 1

    for row in usage_rows:
        factor = equipment_size_factor(row["equipment_type"])
        fuel_amount = cents_from_dollars(random.uniform(180, 800) * factor + 120 * (1 - factor))
        labour_amount = cents_from_dollars(random.uniform(380, 650))

        add_cost(
            usage_id=row["usage_id"],
            job_id=row["job_id"],
            asset_id=row["asset_id"],
            cost_date=row["usage_date"],
            cost_category="Fuel",
            amount_cents=fuel_amount,
            tax_code="GST",
            supplier_name=random.choice(["Ampol", "Caltex", "Viva Energy", "BP Australia"]),
            gst_creditable=True,
        )
        add_cost(
            usage_id=row["usage_id"],
            job_id=row["job_id"],
            asset_id=row["asset_id"],
            cost_date=row["usage_date"],
            cost_category="Labour",
            amount_cents=labour_amount,
            tax_code="N-T",
            supplier_name="Grounded Fleet Payroll",
            gst_creditable=False,
        )
        if random.random() < 0.30:
            add_cost(
                usage_id=row["usage_id"],
                job_id=row["job_id"],
                asset_id=row["asset_id"],
                cost_date=row["usage_date"],
                cost_category="Maintenance",
                amount_cents=cents_from_dollars(random.uniform(200, 900)),
                tax_code="GST",
                supplier_name=random.choice(["Komatsu Service", "CAT Parts", "WesTrac", "Local Diesel Repairs"]),
                gst_creditable=True,
            )
        if row["float_required"]:
            add_cost(
                usage_id=row["usage_id"],
                job_id=row["job_id"],
                asset_id=row["asset_id"],
                cost_date=row["usage_date"],
                cost_category="Transport/float",
                amount_cents=cents_from_dollars(random.uniform(400, 1200)),
                tax_code="GST",
                supplier_name=random.choice(["Grounded Float", "Metro Heavy Haulage", "VIC Tilt Tray"]),
                gst_creditable=True,
            )
        if random.random() < 0.20:
            add_cost(
                usage_id=row["usage_id"],
                job_id=row["job_id"],
                asset_id=row["asset_id"],
                cost_date=row["usage_date"],
                cost_category="E-tag",
                amount_cents=cents_from_dollars(random.uniform(20, 120)),
                tax_code="GST",
                supplier_name="Linkt",
                gst_creditable=True,
            )

    subcontract_jobs = random.sample(jobs, k=max(1, round(len(jobs) * 0.05)))
    usage_by_job = defaultdict(list)
    for row in usage_rows:
        usage_by_job[row["job_id"]].append(row)

    for job in subcontract_jobs:
        job_usage = usage_by_job[job["job_id"]]
        if not job_usage:
            continue
        first_usage = sorted(job_usage, key=lambda item: item["usage_date"])[0]
        amount = cents_from_dollars(random.uniform(800, 3500))
        withholding = round_cents(amount * ABN_WITHHOLDING_RATE)
        add_cost(
            usage_id="",
            job_id=job["job_id"],
            asset_id="",
            cost_date=job["end_date"],
            cost_category="Subcontract ABN",
            amount_cents=amount,
            tax_code="ABN",
            supplier_name=fake.company(),
            gst_creditable=False,
            withholding_cents=withholding,
        )
        payg_rows.append(
            {
                "payg_withholding_id": f"PAYG{len(payg_rows) + 1:04d}",
                "job_id": job["job_id"],
                "cost_id": costs[-1]["cost_id"],
                "supplier_name": costs[-1]["supplier_name"],
                "gross_ex_gst_cents": amount,
                "withholding_rate": f"{ABN_WITHHOLDING_RATE:.2f}",
                "withholding_cents": withholding,
                "liability_account": "PAYG Withholding Payable",
                "bas_field": "W4",
                "note": "47% ABN withholding: 45% base plus 2% Medicare metadata; excluded from GST net calculation",
            }
        )

    return costs, payg_rows


def generate_invoices(jobs: list[dict], revenue_rows: list[dict]) -> list[dict]:
    job_status = {job["job_id"]: job["status"] for job in jobs}
    revenue_by_job_asset = defaultdict(int)
    for row in revenue_rows:
        revenue_by_job_asset[(row["job_id"], row["asset_id"])] += row["total_revenue_cents"]

    invoices = []
    for (job_id, asset_id), amount in sorted(revenue_by_job_asset.items()):
        if job_status[job_id] not in {"Completed", "Invoiced"}:
            continue
        issued_date = fake.date_between(start_date=START_DATE, end_date=END_DATE)
        gst = round_cents(amount * GST_RATE)
        invoices.append(
            {
                "invoice_id": f"INV{len(invoices) + 1:05d}",
                "myob_invoice_number": fake.bothify(text="MYOB-2026-#####").upper(),
                "job_id": job_id,
                "asset_id": asset_id,
                "invoice_date": issued_date.isoformat(),
                "amount_ex_gst_cents": amount,
                "gst_cents": gst,
                "amount_inc_gst_cents": amount + gst,
                "status": random.choices(["Issued", "Paid", "Draft"], weights=[0.70, 0.25, 0.05], k=1)[0],
                "tax_code": "GST",
            }
        )
    return invoices


def generate_payroll_config() -> list[dict]:
    return [
        {
            "config_key": "super_guarantee_rate",
            "config_value": "0.12",
            "effective_from": "2025-07-01",
            "note": "Super guarantee is 12% of ordinary time earnings from 1 Jul 2025",
        },
        {
            "config_key": "vic_payroll_tax_rate",
            "config_value": "0.0485",
            "effective_from": "2026-01-01",
            "note": "VIC payroll tax rate",
        },
        {
            "config_key": "vic_payroll_tax_monthly_threshold",
            "config_value": "83333",
            "effective_from": "2026-01-01",
            "note": "Monthly threshold in dollars; tax applies only to wages above threshold",
        },
        {
            "config_key": "coinvest_rate",
            "config_value": "0.0",
            "effective_from": "2026-01-01",
            "note": "Pending confirmation with industry body",
        },
    ]


def generate_payroll_monthly() -> list[dict]:
    pay_groups = {
        "Operators": (42_000, 55_000),
        "Workshop": (28_000, 36_000),
        "Admin": (18_000, 24_000),
    }
    rows = []
    for month in range(1, 7):
        month_label = date(2026, month, 1).isoformat()
        total_month_wages = 0
        month_rows = []
        for group_name, (low, high) in pay_groups.items():
            gross_wages = cents_from_dollars(random.uniform(low, high))
            super_cents = round_cents(gross_wages * 0.12)
            month_rows.append(
                {
                    "payroll_month_id": f"PAY{month:02d}-{group_name.upper()}",
                    "month_start": month_label,
                    "pay_group": group_name,
                    "gross_wages_cents": gross_wages,
                    "super_guarantee_cents": super_cents,
                    "payroll_tax_cents": 0,
                    "coinvest_cents": 0,
                    "tax_code": "N-T",
                }
            )
            total_month_wages += gross_wages

        threshold_cents = cents_from_dollars(83_333)
        monthly_tax = round_cents(max(0, total_month_wages - threshold_cents) * 0.0485)
        for month_row in month_rows:
            share = month_row["gross_wages_cents"] / total_month_wages
            month_row["payroll_tax_cents"] = round_cents(monthly_tax * share)
            rows.append(month_row)
    return rows


def generate_fuel_tax_credit(cost_rows: list[dict]) -> list[dict]:
    fuel_by_asset_month = defaultdict(int)
    for row in cost_rows:
        if row["cost_category"] == "Fuel":
            fuel_by_asset_month[(row["asset_id"], month_start(date.fromisoformat(row["cost_date"])))] += row[
                "amount_cents"
            ]

    rows = []
    for (asset_id, month), fuel_cost in sorted(fuel_by_asset_month.items()):
        litres = fuel_cost / DIESEL_PRICE_CENTS_PER_LITRE
        credit_cents = round_cents(litres * FUEL_TAX_CREDIT_CENTS_PER_LITRE)
        rows.append(
            {
                "fuel_tax_credit_id": f"FTC{len(rows) + 1:04d}",
                "asset_id": asset_id,
                "month_start": month.isoformat(),
                "fuel_cost_cents": fuel_cost,
                "diesel_price_estimate_cents_per_litre": DIESEL_PRICE_CENTS_PER_LITRE,
                "litres": f"{litres:.2f}",
                "ato_eligible_rate_cents_per_litre": f"{FUEL_TAX_CREDIT_CENTS_PER_LITRE:.2f}",
                "fuel_tax_credit_cents": credit_cents,
                "note": "Placeholder rate; update from ATO every 6 months",
            }
        )
    return rows


def generate_exception_log(
    jobs: list[dict],
    revenue_rows: list[dict],
    invoices: list[dict],
    costs: list[dict],
    payg_rows: list[dict],
) -> list[dict]:
    exceptions = []
    job_ids = {job["job_id"] for job in jobs}

    revenue_by_job_asset = defaultdict(int)
    for row in revenue_rows:
        revenue_by_job_asset[(row["job_id"], row["asset_id"])] += row["total_revenue_cents"]

    invoice_by_job_asset = defaultdict(int)
    for row in invoices:
        invoice_by_job_asset[(row["job_id"], row["asset_id"])] += row["amount_ex_gst_cents"]

    for combo, earned in sorted(revenue_by_job_asset.items()):
        invoiced = invoice_by_job_asset.get(combo, 0)
        if invoiced and invoiced < earned:
            exceptions.append(
                exception_row("UNDERBILLING", combo[0], combo[1], earned - invoiced, "Invoice below earned revenue")
            )
        if invoiced > earned:
            exceptions.append(
                exception_row("OVERBILLING", combo[0], combo[1], invoiced - earned, "Invoice above earned revenue")
            )

    payg_cost_ids = {row["cost_id"] for row in payg_rows}
    for row in costs:
        if row["job_id"] not in job_ids:
            exceptions.append(
                exception_row("ORPHAN_COST", row["job_id"], row["asset_id"], int(row["amount_cents"]), "Cost has no valid job_id")
            )
        if row["tax_code"] == "ABN" and row["cost_id"] not in payg_cost_ids:
            exceptions.append(
                exception_row(
                    "NO_ABN_WITHHOLDING",
                    row["job_id"],
                    row["asset_id"],
                    int(row["amount_cents"]),
                    "ABN tax-code cost missing PAYG withholding row",
                )
            )

    return exceptions


def exception_row(
    exception_type: str,
    job_id: str,
    asset_id: str,
    amount_cents: int,
    message: str,
) -> dict:
    return {
        "exception_id": "",
        "exception_type": exception_type,
        "job_id": job_id,
        "asset_id": asset_id,
        "amount_cents": amount_cents,
        "message": message,
    }


def number_exceptions(rows: list[dict]) -> list[dict]:
    for idx, row in enumerate(rows, start=1):
        row["exception_id"] = f"EXC{idx:05d}"
    return rows


def print_summary(table_rows: dict[str, list[dict]], revenue_rows: list[dict], exception_rows: list[dict]) -> None:
    total_revenue = sum(row["total_revenue_cents"] for row in revenue_rows)
    print("\nSynthetic data generated in data/csv/\n")
    print("Table row counts")
    print("----------------")
    for table_name in sorted(table_rows):
        print(f"{table_name:<24} {len(table_rows[table_name]):>8,}")
    print("----------------")
    print(f"{'total_revenue_ex_gst':<24} ${total_revenue / 100:>11,.2f}")

    flags = defaultdict(int)
    for row in exception_rows:
        flags[row["exception_type"]] += 1

    print("\nException flags")
    print("---------------")
    for name in ["UNDERBILLING", "OVERBILLING", "NO_ABN_WITHHOLDING", "ORPHAN_COST"]:
        print(f"{name:<24} {flags[name]:>8,}")


def main() -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    rate_by_type = {item.equipment_type: item for item in RATE_CARD}

    rate_card = generate_rate_card()
    fleet_register = generate_fleet_register()
    job_master = generate_job_master()
    usage_log = generate_usage_log(job_master)
    job_rates = generate_job_rates(usage_log, rate_by_type)
    revenue_engine = generate_revenue_engine(usage_log, job_rates, rate_by_type)
    costs, payg_withholding = generate_costs(usage_log, job_master)
    invoice_myob = generate_invoices(job_master, revenue_engine)
    payroll_config = generate_payroll_config()
    payroll_monthly = generate_payroll_monthly()
    fuel_tax_credit = generate_fuel_tax_credit(costs)
    exception_log = number_exceptions(
        generate_exception_log(job_master, revenue_engine, invoice_myob, costs, payg_withholding)
    )

    table_rows = {
        "rate_card": rate_card,
        "fleet_register": fleet_register,
        "job_master": job_master,
        "usage_log": usage_log,
        "job_rates": job_rates,
        "revenue_engine": revenue_engine,
        "costs": costs,
        "invoice_myob": invoice_myob,
        "payroll_config": payroll_config,
        "payroll_monthly": payroll_monthly,
        "payg_withholding": payg_withholding,
        "fuel_tax_credit": fuel_tax_credit,
        "exception_log": exception_log,
    }

    for table_name, rows in table_rows.items():
        csv_write(table_name, rows)

    print_summary(table_rows, revenue_engine, exception_log)


if __name__ == "__main__":
    main()
