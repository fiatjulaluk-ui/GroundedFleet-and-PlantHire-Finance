"""Formatting helpers for the Grounded Finance Dashboard."""

from __future__ import annotations


BRAND = {
    "primary": "#1A9E8A",
    "sage": "#8CC9A0",
    "background": "#F8F8F5",
    "text": "#2C2C2A",
    "warning": "#BA7517",
    "error": "#A32D2D",
    "grey": "#777772",
}


def fmt_currency(cents) -> str:
    value = 0 if cents is None else float(cents) / 100
    return f"${value:,.2f}"


def fmt_pct(value) -> str:
    if value is None:
        value = 0
    return f"{float(value):.1f}%"


def fmt_hours(value) -> str:
    if value is None:
        value = 0
    return f"{float(value):.1f} hrs"


def colour_margin(pct) -> str:
    pct = 0 if pct is None else float(pct)
    if pct < 20:
        return BRAND["error"]
    if pct < 40:
        return BRAND["warning"]
    return BRAND["primary"]


def status_colour(status: str) -> str:
    status = str(status or "").upper()
    if status in {"OK", "BALANCED", "RESOLVED", "LOW"}:
        return BRAND["primary"]
    if status in {"UNDERBILLED", "CHECK", "MEDIUM"}:
        return BRAND["warning"]
    if status in {"OVERBILLED", "IMBALANCED", "HIGH"}:
        return BRAND["error"]
    return BRAND["grey"]


def status_badge(status) -> str:
    label = str(status or "Unknown")
    colour = status_colour(label)
    return (
        f"<span style='display:inline-block;padding:0.2rem 0.55rem;border-radius:999px;"
        f"background:{colour};color:white;font-size:0.78rem;font-weight:700'>{label}</span>"
    )


def money_columns(df, columns):
    out = df.copy()
    for col in columns:
        if col in out:
            out[col] = out[col].apply(fmt_currency)
    return out
