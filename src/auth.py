from __future__ import annotations

import os
import streamlit as st

DEFAULT_DEMO_PASSWORD = "enterprise-demo-2026"


def get_expected_password() -> str:
    try:
        return st.secrets.get("APP_PASSWORD") or os.getenv("APP_PASSWORD") or DEFAULT_DEMO_PASSWORD
    except Exception:
        return os.getenv("APP_PASSWORD") or DEFAULT_DEMO_PASSWORD


def require_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("Enterprise Document Brand Auditor")
    st.caption("Password-protected case study app")
    entered = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        if entered == get_expected_password():
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False
