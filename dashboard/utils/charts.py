"""Plotly chart helpers styled with Grounded brand colours."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from .formatting import BRAND


def _style(fig):
    fig.update_layout(
        font_family="Arial",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[BRAND["primary"], BRAND["sage"], BRAND["warning"], BRAND["error"]],
        margin=dict(l=10, r=10, t=35, b=10),
    )
    return fig


def revenue_bar(df, x, y, title="", orientation="v"):
    fig = px.bar(df, x=x, y=y, title=title, orientation=orientation, color_discrete_sequence=[BRAND["primary"]])
    return _style(fig)


def wip_bar(df, x, y, title=""):
    fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=[BRAND["warning"]])
    return _style(fig)


def profit_scatter(df, x, y, size, color=None, title=""):
    fig = px.scatter(
        df,
        x=x,
        y=y,
        size=size,
        color=color,
        title=title,
        color_discrete_sequence=[BRAND["primary"], BRAND["warning"], BRAND["error"], BRAND["sage"]],
    )
    return _style(fig)


def waterfall(labels, values, title=""):
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            increasing={"marker": {"color": BRAND["primary"]}},
            decreasing={"marker": {"color": BRAND["error"]}},
            totals={"marker": {"color": BRAND["sage"]}},
        )
    )
    fig.update_layout(title=title)
    return _style(fig)


def trend_line(df, x, y, title=""):
    fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=[BRAND["primary"]])
    fig.update_traces(marker_line_width=0)
    return _style(fig)
