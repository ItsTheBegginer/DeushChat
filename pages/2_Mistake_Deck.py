import random
from collections import Counter
from datetime import date

import streamlit as st

from core import db
from core.db import get_or_create_db

st.set_page_config(page_title="Mistake Deck — Deutschfreund", page_icon="🗂️", layout="wide")

# Initialise DB (idempotent)
get_or_create_db()

st.title("🗂️ Mistake Deck")
st.caption("Review the corrections from your chat sessions using spaced repetition.")

# ─────────────────────────────────────────────────────────────────
# Error-type tips
# ─────────────────────────────────────────────────────────────────
ERROR_TIPS = {
    "word_order": "💡 Verb goes in second position in German. Example: *Ich gehe heute* not *Ich heute gehe*.",
    "gender": "💡 German has three genders: der (m), die (f), das (n). They must be memorised with each noun.",
    "verb_conjugation": "💡 Verbs change ending by subject: ich gehe, du gehst, er geht.",
    "case": "💡 German has 4 cases. Accusative changes der → den for masculine nouns.",
    "vocabulary": "💡 Keep adding words from real life — the more context, the better they stick.",
}

# ─────────────────────────────────────────────────────────────────
# Session-state initialisation
# ─────────────────────────────────────────────────────────────────
if "got_it_count" not in st.session_state:
    st.session_state.got_it_count = 0
if "try_again_count" not in st.session_state:
    st.session_state.try_again_count = 0

# ─────────────────────────────────────────────────────────────────
# Feature 1 — Streak tracker
# ─────────────────────────────────────────────────────────────────
streak = db.get_streak()
if streak > 0:
    st.markdown(f"🔥 **{streak}-day streak!** Keep going!")
else:
    st.markdown("Start your streak today — complete a review session!")

# ─────────────────────────────────────────────────────────────────
# Feature 2 — Progress stats bar
# ─────────────────────────────────────────────────────────────────
stats = db.get_card_stats()
total_reviewed_session = st.session_state.got_it_count + st.session_state.try_again_count
if total_reviewed_session > 0:
    accuracy_str = f"{round(st.session_state.got_it_count / total_reviewed_session * 100)}%"
else:
    accuracy_str = "—"

col1, col2, col3 = st.columns(3)
col1.metric("📚 Total cards", stats["total"])
col2.metric("🏆 Mastered", stats["mastered"])
col3.metric("✅ Session accuracy", accuracy_str)

st.divider()

# ─────────────────────────────────────────────────────────────────
# Feature 3 — Error-type filter
# ─────────────────────────────────────────────────────────────────
due_counts = db.get_due_counts_by_type()
filter_options = ["All types"] + [
    f"{et} ({cnt} due)" for et, cnt in sorted(due_counts.items())
]

# Detect filter change to reset deck
prev_filter = st.session_state.get("selected_filter", "All types")
selected_filter = st.selectbox(
    "Filter by error type",
    options=filter_options,
    key="selected_filter",
)
if selected_filter != prev_filter:
    for key in ("review_cards", "review_index", "card_flipped"):
        if key in st.session_state:
            del st.session_state[key]

# ─────────────────────────────────────────────────────────────────
# Load cards based on filter
# ─────────────────────────────────────────────────────────────────
if "review_cards" not in st.session_state:
    if selected_filter == "All types":
        cards = db.get_due_cards()
    else:
        error_type = selected_filter.split(" (")[0]
        cards = db.get_due_cards_by_type(error_type)
    random.shuffle(cards)
    st.session_state.review_cards = cards
    st.session_state.review_index = 0
    st.session_state.card_flipped = False

review_cards: list[dict] = st.session_state.review_cards
review_index: int = st.session_state.review_index
card_flipped: bool = st.session_state.card_flipped

# ─────────────────────────────────────────────────────────────────
# Feature 4 & 5 — Card review + session summary
# ─────────────────────────────────────────────────────────────────
if not review_cards:
    st.success("No cards due today! Come back tomorrow. 🎉")
elif review_index >= len(review_cards):
    # ── Feature 5: Session summary ──
    db.update_streak()
    st.balloons()

    total_session = st.session_state.got_it_count + st.session_state.try_again_count
    if total_session > 0:
        pct = round(st.session_state.got_it_count / total_session * 100)
        if pct >= 80:
            grade_msg = "Excellent! 🌟"
        elif pct >= 50:
            grade_msg = "Good progress! 💪"
        else:
            grade_msg = "Keep at it — repetition is the key! 📖"
    else:
        pct = 0
        grade_msg = ""

    st.success(f"Session complete! You reviewed {len(review_cards)} card{'s' if len(review_cards) != 1 else ''}.")

    st.markdown(f"""
**Cards reviewed:** {len(review_cards)}  
**Got it:** {st.session_state.got_it_count} &nbsp;|&nbsp; **Try again:** {st.session_state.try_again_count}  
**Accuracy:** {pct}% — {grade_msg}
""")

    # Error types breakdown for this session
    type_counter: Counter = Counter(c["error_type"] for c in review_cards)
    if type_counter:
        st.markdown("**Error types in this session:**")
        for et, cnt in type_counter.most_common():
            st.markdown(f"- {et.replace('_', ' ').title()}: {cnt}")

    if st.button("Reload deck", key="reload_btn"):
        st.session_state.got_it_count = 0
        st.session_state.try_again_count = 0
        for key in ("review_cards", "review_index", "card_flipped"):
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
else:
    card = review_cards[review_index]

    # Progress bar
    st.progress(review_index / len(review_cards))
    st.caption(f"Card {review_index + 1} of {len(review_cards)}")

    st.divider()

    # Card front + error type badge
    st.markdown(f"**{card['front']}**")
    st.caption(f"Error type: {card['error_type'].replace('_', ' ').title()}")

    if not card_flipped:
        if st.button("Reveal answer", key="reveal_btn"):
            st.session_state.card_flipped = True
            st.rerun()
    else:
        st.markdown(card["back"])
        st.divider()

        col_got, col_try = st.columns(2)
        with col_got:
            if st.button("✅ Got it", key="got_it_btn", use_container_width=True):
                db.update_card_review(card["id"], got_it=True)
                st.session_state.got_it_count += 1
                st.session_state.review_index += 1
                st.session_state.card_flipped = False
                st.rerun()
        with col_try:
            if st.button("❌ Try again", key="try_again_btn", use_container_width=True):
                db.update_card_review(card["id"], got_it=False)
                st.session_state.try_again_count += 1
                st.session_state.review_index += 1
                st.session_state.card_flipped = False
                st.rerun()

# ─────────────────────────────────────────────────────────────────
# Feature 6 — Insights panel
# ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Your error patterns")

error_stats = db.get_error_stats()

if not error_stats:
    st.info("No corrections recorded yet. Practice a scenario to build your Mistake Deck.")
else:
    chart_data = {row["error_type"]: row["count"] for row in error_stats}
    st.bar_chart(chart_data)

    st.markdown("**Breakdown:**")
    for row in error_stats:
        label = row["error_type"].replace("_", " ").title()
        st.markdown(f"- **{label}**: {row['count']} card{'s' if row['count'] != 1 else ''}")

    # Tip for top error type
    top_error = error_stats[0]["error_type"]
    if top_error in ERROR_TIPS:
        st.info(ERROR_TIPS[top_error])

# ─────────────────────────────────────────────────────────────────
# Feature 7 — Browse all cards expander
# ─────────────────────────────────────────────────────────────────
st.divider()
with st.expander("🔍 Browse all cards"):
    search_text = st.text_input("Search cards", key="card_search")
    all_cards = db.get_all_cards()

    if search_text:
        needle = search_text.lower()
        all_cards = [
            c for c in all_cards
            if needle in c["front"].lower() or needle in c["back"].lower()
        ]

    if not all_cards:
        st.info("No cards yet.")
    else:
        for card in all_cards:
            with st.container():
                st.markdown(f"**{card['front']}**")
                st.caption(
                    f"Type: {card['error_type']} | "
                    f"Scenario: {card['source_scenario'] or 'N/A'} | "
                    f"Next review: {card['next_review']}"
                )
                with st.expander("Show answer"):
                    st.markdown(card["back"])
