"""Small visual components and charts; all user text is escaped."""
from html import escape
from itertools import groupby
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html as component_html
from app.experiments import SLEEP, WAKE, RATING, PERIODS

STAGE_COLOURS = {"W": "#d5ae7e", "N1": "#c9c0e1", "N2": "#9a8aba", "N3": "#51446e", "REM": "#7d9b9a"}
STAGE_NAMES = {"W": "Awake", "N1": "Light (N1)", "N2": "Light (N2)", "N3": "Deep", "REM": "REM"}
OUTCOME_NAMES = {SLEEP: "Estimated sleep", WAKE: "Wake during sleep", RATING: "Morning restfulness"}


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def open_page_at_top(route):
    """Reset scrolling on navigation, preserving it during edits on one page."""
    if st.session_state.get("_rendered_route") != route:
        st.session_state["_rendered_route"] = route
        st.session_state["_navigation_serial"] = st.session_state.get("_navigation_serial", 0) + 1
    # The serial changes the iframe source only on navigation. An identical
    # source can be reused by React, so its script would not run on the next
    # screen. Keeping the component mounted also avoids layout jumps on edits.
    serial = st.session_state.get("_navigation_serial", 0)
    component_html(f"<!-- navigation {serial} -->" + """
        <script>
        requestAnimationFrame(() => requestAnimationFrame(() => {
            const page = window.parent.document.querySelector('[data-testid="stMain"]');
            if (page) page.scrollTo({top: 0, behavior: "instant"});
        }));
        </script>
    """, height=0, scrolling=False)


def hero(kicker, title, text, dark=False):
    html(f'<div class="hero{" dark" if dark else ""}"><div class="overline">{escape(kicker)}</div>'
         f'<h2>{escape(title)}</h2><p>{escape(text)}</p></div>')


def card(kicker, title, text, symbol=""):
    info_cards([(kicker, title, text, symbol)])


def metric_card(label, value, note):
    metric_cards([(label, value, note)])


def _card_grid(cards, kind, columns):
    """One HTML grid owns the row height, independent of Streamlit wrappers."""
    if not cards:
        return
    count = min(len(cards), 3) if columns is None else columns
    if type(count) is not int or not 1 <= count <= 4:
        raise ValueError("Card groups need between one and four columns.")
    html(f'<div class="nj-card-grid nj-card-grid--{kind}" '
         f'style="--nj-card-columns:{count}" role="list">'
         + "".join(cards) + '</div>')


def metric_cards(items, columns=None):
    """Render equal-size metrics from (label, formatted value, note) tuples."""
    cards = [
        '<div class="card nj-metric-card" role="listitem">'
        f'<div class="label">{escape(str(label))}</div>'
        f'<div class="big-number">{escape(str(value))}</div>'
        f'<div class="small-note">{escape(str(note))}</div></div>'
        for label, value, note in items
    ]
    _card_grid(cards, "metrics", columns)


def info_cards(items, columns=None):
    """Render equal-size descriptions from (kicker, title, text[, symbol]) tuples."""
    cards = []
    for item in items:
        kicker, title, text, *symbols = item
        if len(symbols) > 1:
            raise ValueError("An information card accepts at most one symbol.")
        symbol = symbols[0] if symbols else ""
        icon = f'<div class="symbol" aria-hidden="true">{escape(str(symbol))}</div>' if symbol else ""
        cards.append(
            '<div class="card nj-info-card" role="listitem">'
            f'<div class="overline">{escape(str(kicker))}</div>'
            + icon + f'<h3>{escape(str(title))}</h3><p>{escape(str(text))}</p></div>'
        )
    _card_grid(cards, "information", columns)


def minutes_text(value):
    if value is None or pd.isna(value):
        return "Not available"
    total = int(round(value))
    minutes = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{total // 60}h {total % 60:02d}m" if total >= 60 else f"{minutes} min"


def outcome_value(value, outcome):
    if value is None or pd.isna(value):
        return "Not recorded"
    return f"{value:.1f} / 5" if outcome == RATING else minutes_text(value)


def sleep_ribbon(stages):
    runs = [(stage, sum(1 for _ in group)) for stage, group in groupby(stages)]
    html('<div class="night-strip" role="img" aria-label="Estimated stages through the recording">' +
         "".join(f'<span style="width:{n/len(stages)*100:.6f}%;background:{STAGE_COLOURS[s]}" '
                 f'title="{STAGE_NAMES[s]}: {n*.5:g} minutes"></span>' for s, n in runs) + '</div>')
    html('<div class="strip-legend">' + "".join(
        f'<span><span style="color:{c}">●</span> {STAGE_NAMES[s]}</span>' for s, c in STAGE_COLOURS.items()) + '</div>')


def timeline_chart(stages):
    order = ["W", "REM", "N1", "N2", "N3"]
    fig = go.Figure(go.Scatter(
        x=[i / 120 for i in range(len(stages) + 1)],
        y=[order.index(s) for s in stages + [stages[-1]]], mode="lines",
        line=dict(shape="hv", color="#6956a5", width=2),
        customdata=[STAGE_NAMES[s] for s in stages + [stages[-1]]],
        hovertemplate="%{x:.2f} hours from start<br>%{customdata}<extra></extra>"))
    fig.update_layout(height=250, xaxis_title="Hours from recording start",
                      yaxis=dict(tickvals=list(range(5)), ticktext=[STAGE_NAMES[s] for s in order], range=[4.4, -.4]))
    chart_style(fig)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def comparison_chart(nights, outcome):
    eligible = nights[nights.Date.notna() & nights.Period.isin(PERIODS)].copy()
    fig = go.Figure()
    for period, colour, name, symbol, dash in zip(
        PERIODS, ("#7d738b", "#6956a5"), ("Before the change", "With the change"),
        ("circle", "diamond"), ("dot", "solid"),
    ):
        rows = eligible.loc[eligible.Period == period].sort_values("Date")
        fig.add_trace(go.Scatter(
            x=rows.Date, y=pd.to_numeric(rows[outcome], errors="coerce"), mode="markers+lines", name=name,
            marker=dict(color=colour, size=11, symbol=symbol, line=dict(color="#fff", width=2)),
            line=dict(color=colour, width=1.5, dash=dash),
            hovertemplate="%{x}<br>%{y:.1f}" + (" / 5" if outcome == RATING else " min") + "<extra></extra>"))
    fig.update_layout(height=270, yaxis_title=OUTCOME_NAMES[outcome] + (" (1–5)" if outcome == RATING else " (minutes)"),
                      legend=dict(orientation="h", y=1.22, x=0), xaxis_title=None)
    if outcome == RATING:
        fig.update_yaxes(range=[.7, 5.3], dtick=1)
    chart_style(fig)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def chart_style(fig):
    fig.update_layout(margin=dict(l=5, r=5, t=40, b=5),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Arial, sans-serif", size=12, color="#6c6b7c"))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#eae6f0", zeroline=False)
