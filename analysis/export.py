"""Excel and PDF exports for finance-control outputs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .compliance import build_bas_check, build_journal_pack
from .cost_allocation import build_asset_profit, build_job_profit
from .db import get_df
from .exceptions import scan_exceptions


def _period_bounds(period: str | date) -> tuple[date, date]:
    start = pd.to_datetime(period).date().replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(1)).date()
    return start, end


def export_excel(period: str | date, output_path: str | Path) -> None:
    """Write a multi-sheet Excel workbook for the period."""

    start, end = _period_bounds(period)
    revenue = get_df(
        """
        SELECT *
        FROM revenue_engine
        WHERE usage_date BETWEEN :start AND :end
        ORDER BY usage_date, job_id, asset_id
        """,
        {"start": start, "end": end},
    )
    wip = get_df("SELECT * FROM wip_summary ORDER BY wip_cents DESC")
    job_profit = build_job_profit(period)
    asset_profit = build_asset_profit(period)
    bas = build_bas_check(period)
    journal_pack = build_journal_pack(period)
    exceptions = scan_exceptions(period)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        revenue.to_excel(writer, sheet_name="Revenue", index=False)
        wip.to_excel(writer, sheet_name="WIP", index=False)
        job_profit.to_excel(writer, sheet_name="Job Profit", index=False)
        asset_profit.to_excel(writer, sheet_name="Asset Profit", index=False)
        bas.to_excel(writer, sheet_name="BAS", index=False)
        journal_pack.to_excel(writer, sheet_name="Journal Pack", index=False)
        exceptions.to_excel(writer, sheet_name="Exceptions", index=False)


def export_pdf_summary(period: str | date, output_path: str | Path) -> None:
    """Write a one-page PDF summary for the period."""

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    start, _ = _period_bounds(period)
    bas = build_bas_check(period).iloc[0]
    job_profit = build_job_profit(period)
    exceptions = scan_exceptions(period)

    revenue = int(job_profit["revenue"].sum()) if not job_profit.empty else 0
    cost = int(job_profit["total_cost"].sum()) if not job_profit.empty else 0
    profit = int(job_profit["profit"].sum()) if not job_profit.empty else 0
    margin = 0 if revenue == 0 else profit / revenue * 100

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Grounded Fleet & Plant Hire Finance Summary")
    y -= 28
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Period: {start:%B %Y}")
    y -= 34

    lines = [
        ("Revenue ex-GST", revenue),
        ("Direct costs", cost),
        ("Profit", profit),
        ("Margin %", f"{margin:.2f}%"),
        ("BAS G1", int(bas["G1"])),
        ("BAS 1A", int(bas["1A"])),
        ("BAS 1B", int(bas["1B"])),
        ("Net GST", int(bas["Net GST"])),
        ("PAYG W4", int(bas["W4"])),
        ("Open exceptions", len(exceptions)),
    ]

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Key Metrics")
    y -= 18
    pdf.setFont("Helvetica", 10)
    for label, value in lines:
        display = f"${value / 100:,.2f}" if isinstance(value, int) else str(value)
        if label == "Open exceptions":
            display = str(value)
        pdf.drawString(60, y, label)
        pdf.drawRightString(width - 60, y, display)
        y -= 18

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 55, "Amounts are stored in cents in the database; this summary displays dollars.")
    pdf.showPage()
    pdf.save()
