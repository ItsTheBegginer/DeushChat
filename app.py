import streamlit as st

# st.set_page_config must be the FIRST Streamlit call
st.set_page_config(page_title="DeushChat", page_icon="🇩🇪", layout="wide")

import sqlite3
from pathlib import Path

import core.db as db

# Initialise DB on every run (idempotent)
db.get_or_create_db()

profile = db.get_profile()

if profile is None:
    # ── ONBOARDING FORM (first run) ──────────────────────────────────────────
    st.title("Willkommen! 👋 Let's get you set up.")

    with st.form("onboarding"):
        name = st.text_input("Your first name")
        level = st.selectbox("Your current German level", ["A0", "A1", "A2", "B1"])
        city = st.text_input("Target city or university (optional)")
        goal = st.selectbox(
            "Your main goal",
            [
                "Survive daily life in Germany",
                "Pass university admission",
                "Both",
            ],
        )
        submitted = st.form_submit_button("Start learning!")

    if submitted and name:
        goal_key = {
            "Survive daily life in Germany": "daily_life",
            "Pass university admission": "university",
            "Both": "both",
        }[goal]
        db.save_profile(name, level, city, goal_key)
        st.switch_page("pages/1_Scenarios.py")

    elif submitted and not name:
        st.warning("Please enter your first name to continue.")

else:
    # ── WELCOME-BACK DASHBOARD (returning user) ──────────────────────────────
    st.title(f"Hallo, {profile['name']}! 👋")

    # Fetch stats
    due_today = len(db.get_due_cards())

    # Total corrections: COUNT(*) from cards table directly
    db_path = Path.home() / ".deutschfreund" / "deutschfreund.db"
    with sqlite3.connect(db_path) as _conn:
        _cur = _conn.execute("SELECT COUNT(*) FROM cards")
        total_corrections = _cur.fetchone()[0]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Cards due for review today", due_today)
    with col2:
        st.metric("Total corrections saved", total_corrections)

    st.divider()
    st.subheader("Where would you like to go?")

    nav_col1, nav_col2, nav_col3 = st.columns(3)
    with nav_col1:
        st.page_link("pages/1_Scenarios.py", label="🎭 Scenarios", icon="🎭")
    with nav_col2:
        st.page_link("pages/2_Mistake_Deck.py", label="🃏 Mistake Deck", icon="🃏")
    with nav_col3:
        st.page_link("pages/3_Words_from_Life.py", label="📖 Words from Life", icon="📖")
