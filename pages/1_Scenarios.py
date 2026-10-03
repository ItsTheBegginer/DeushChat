import json
import uuid

import streamlit as st

from core import db, llm
from core.db import get_or_create_db
from data.scenarios import SCENARIOS

st.set_page_config(page_title="Scenarios — Deutschfreund", page_icon="🎭", layout="wide")

# Initialise DB (idempotent)
get_or_create_db()

# Guard: require a profile
profile = db.get_profile()
if profile is None:
    st.switch_page("app.py")

# ─────────────────────────────────────────────────────────────────
# GRID VIEW — no active scenario
# ─────────────────────────────────────────────────────────────────
if st.session_state.get("active_scenario") is None:
    st.title("🎭 Choose a Scenario")
    st.caption("Pick a real-life situation to practice. Each scenario has goals to complete.")

    cols = st.columns(4)
    for i, scenario in enumerate(SCENARIOS):
        with cols[i % 4]:
            label = f"{scenario['emoji']} **{scenario['name']}**\n\n`{scenario['difficulty']}`"
            if st.button(label, key=scenario["id"], use_container_width=True):
                st.session_state.active_scenario = scenario
                st.session_state.chat_history = []
                st.session_state.completed_goals = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.show_hint = False
                st.rerun()

# ─────────────────────────────────────────────────────────────────
# CHAT VIEW — active scenario selected
# ─────────────────────────────────────────────────────────────────
else:
    scenario = st.session_state.active_scenario
    chat_history: list[dict] = st.session_state.chat_history
    completed_goals: list[int] = st.session_state.completed_goals

    # ── Header ──────────────────────────────────────────────────
    col_title, col_back = st.columns([8, 2])
    with col_title:
        st.title(f"{scenario['emoji']} {scenario['name']}  `{scenario['difficulty']}`")
    with col_back:
        st.write("")  # vertical spacing
        if st.button("← Back to scenarios", key="back_btn"):
            del st.session_state["active_scenario"]
            st.rerun()

    # ── Setup card ──────────────────────────────────────────────
    st.info(f"**Situation:** {scenario['setup_en']}")

    # ── Goals tracker ───────────────────────────────────────────
    goals = scenario["goals"]
    goal_lines = [
        f"{'✅' if i in completed_goals else '⬜'} {goal}"
        for i, goal in enumerate(goals)
    ]
    with st.expander("📋 Goals", expanded=True):
        for line in goal_lines:
            st.markdown(line)

    st.divider()

    # ── Chat history ────────────────────────────────────────────
    for msg in chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
                # Correction panel — only when error_type is not 'none'
                correction = msg.get("correction")
                if correction and correction.get("error_type", "none") != "none":
                    with st.expander("📝 Correction", expanded=True):
                        st.markdown(
                            f"**You wrote:** {correction['original']}  \n"
                            f"**Corrected:** {correction['corrected']}"
                        )
                        st.markdown(f"**Why:** {correction['reason']}")
                        # Error-type badge using colored markdown
                        badge_colors = {
                            "word_order": "🔵",
                            "gender": "🟣",
                            "verb_conjugation": "🟠",
                            "case": "🔴",
                            "vocabulary": "🟢",
                        }
                        badge = badge_colors.get(correction["error_type"], "⚪")
                        st.markdown(
                            f"{badge} `{correction['error_type'].replace('_', ' ').title()}`"
                        )
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])

    # ── Hint button ─────────────────────────────────────────────
    # Find the last assistant message for hint data
    last_assistant = next(
        (m for m in reversed(chat_history) if m["role"] == "assistant"), None
    )

    if last_assistant:
        hint_text = last_assistant.get("hint", "")
        hint_translation = last_assistant.get("hint_translation", "")

        if not st.session_state.get("show_hint", False):
            if st.button("💡 Show Hint", key="hint_btn"):
                st.session_state.show_hint = True
                st.rerun()
        else:
            if hint_text:
                st.info(
                    f"💡 **Suggested reply:** {hint_text}\n\n"
                    f"*(Translation of AI's last line: {hint_translation})*"
                )
            if st.button("Hide hint", key="hide_hint_btn"):
                st.session_state.show_hint = False
                st.rerun()

    # ── Chat input ──────────────────────────────────────────────
    user_input = st.chat_input("Type your German reply…")

    if user_input:
        # Guard: Ollama must be running
        if not llm.check_ollama_running():
            st.error(
                "⚠️ Ollama is not running. Start it with: `ollama serve`\n\n"
                "Then refresh this page."
            )
            st.stop()

        # Build llm_history: only {role, content} — no correction dicts
        llm_history = [
            {"role": m["role"], "content": m["content"]}
            for m in chat_history
        ]

        # Call LLM
        result = llm.get_scenario_reply(
            profile,
            scenario,
            completed_goals,
            llm_history,
            user_input,
        )

        correction = result.get("correction", {})
        reply = result.get("reply", "")
        hint = result.get("hint", "")
        hint_translation = result.get("hint_translation", "")
        goals_completed_new = result.get("goals_completed", [])

        # Append user message (with correction attached)
        chat_history.append(
            {
                "role": "user",
                "content": user_input,
                "correction": correction,
            }
        )

        # Append assistant message
        chat_history.append(
            {
                "role": "assistant",
                "content": reply,
                "hint": hint,
                "hint_translation": hint_translation,
            }
        )

        # Merge newly completed goals (set union)
        for idx in goals_completed_new:
            if idx not in completed_goals:
                completed_goals.append(idx)

        # Save correction as flashcard when there is a real error
        error_type = correction.get("error_type", "none")
        if error_type != "none":
            db.save_card(
                front=correction.get("original", user_input),
                back=correction.get("corrected", user_input) + "\n" + correction.get("reason", ""),
                error_type=error_type,
                source_scenario=scenario["id"],
            )

        # Persist both messages to DB
        session_id = st.session_state.session_id
        scenario_id = scenario["id"]
        db.save_message(session_id, scenario_id, "user", user_input, json.dumps(correction))
        db.save_message(session_id, scenario_id, "assistant", reply, None)

        # Reset hint visibility for the new turn
        st.session_state.show_hint = False

        # Persist updated lists back into session_state
        st.session_state.chat_history = chat_history
        st.session_state.completed_goals = completed_goals

        st.rerun()
