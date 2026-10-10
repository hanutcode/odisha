"""Live version of the demo for development: `streamlit run demo/app.py`.

Rebuilds the same offline HTML on every run, so what the team sees here is
exactly what runs at the fair. Also shows the contract table and checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from hcm import contract  # noqa: E402
import build_static  # noqa: E402

st.set_page_config(page_title="Odisha Hidden Risk Map", layout="wide")

try:
    est, rc = contract.load()
except FileNotFoundError:
    st.error("No model outputs yet. Run `make mock` for test data, or let Hanut's model write outputs/.")
    st.stop()
except contract.ContractError as e:
    st.error(f"Model outputs break the contract: {e}")
    st.stop()

if contract.is_mock(est):
    st.warning("MOCK DATA — for building the tool only. Not results.")

html_path = build_static.build()
components.html(html_path.read_text(encoding="utf-8"), height=1050, scrolling=True)

with st.expander("Contract data (outputs/district_estimates.csv)"):
    st.dataframe(est, use_container_width=True, hide_index=True)
with st.expander("Reason codes (outputs/reason_codes.csv)"):
    st.dataframe(rc, use_container_width=True, hide_index=True)
    if not rc["odia_checked"].all():
        st.info("Some Odia reason texts are not checked by the Odia speaker yet.")

st.download_button("Download offline HTML for the fair", html_path.read_bytes(),
                   file_name="odisha_demo.html", mime="text/html")
