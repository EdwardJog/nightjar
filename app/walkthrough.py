"""Presentation-only focus for the practice guide; no model or storage access."""
import json
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as component_html


def render_walkthrough_focus():
    """Keep one component mounted so skip/exit also remove browser restrictions."""
    focus = st.session_state.get("demo_focus") if st.session_state.get("demo") else None
    payload = json.dumps(focus).replace("<", "\\u003c")
    script = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")
    component_html(f"<script>const tour = {payload};\n{script}</script>",
                   height=0, scrolling=False)
