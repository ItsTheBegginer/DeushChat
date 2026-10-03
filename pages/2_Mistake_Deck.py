import random

import streamlit as st

from core import db
from core.db import get_or_create_db

st.set_page_config(page_title="Mistake Deck — Deutschfreund", page_icon="🗂️", layout="wide")

# Initialise DB (idempotent)
get_or_create_db()

st.title("🗂️ Mistake Deck")
st.caption("Review the corrections from your chat sessions using spaced repetition.")

# ─────────────────────────────────────────────────────────────────
# Load due cards once per session
# ─────────────────────────────────────────────────────────────────
if "review_cards" not in st.session_state:
    cards = db.get_due_cards()
    random.shuffle(cards)
    st.session_state.review_cards = cards
    st.session_state.review_index = 0
    st.session_state.card_flipped = False

review_cards: list[dict] = st.session_state.review_cards
review_index: int = st.session_state.review_index
card_flipped: bool = st.session_state.card_flipped

# ─────────────────────────────────────────────────────────────────
# Review section
# ─────────────────────────────────────────────────────────────────
if not review_cards:
    st.success("No cards due today! Come back tomorrow. 🎉")
elif review_index >= len(review_cards):
    # Session complete
    st.balloons()
    st.success(f"You reviewed {len(review_cards)} card{'s' if len(review_cards) != 1 else ''}. Well done! 🎉")
    if st.button("Reload deck", key="reload_btn"):
        # Reset for a fresh load
        del st.session_state["review_cards"]
        st.rerun()
else:
    card = review_cards[review_index]

    # Progress bar
    st.progress(review_index / len(review_cards))
    st.caption(f"Card {review_index + 1} of {len(review_cards)}")

    st.divider()

    # Card front
    st.markdown(f"**{card['front']}**")

    if not card_flipped:
        # Show reveal button
        if st.button("Reveal answer", key="reveal_btn"):
            st.session_state.card_flipped = True
            st.rerun()
    else:
        # Show card back
        st.markdown(card["back"])
        st.divider()

        # Got it / Try again side by side
        col_got, col_try = st.columns(2)
        with col_got:
            if st.button("✅ Got it", key="got_it_btn", use_container_width=True):
                db.update_card_review(card["id"], got_it=True)
                st.session_state.review_index += 1
                st.session_state.card_flipped = False
                st.rerun()
        with col_try:
            if st.button("❌ Try again", key="try_again_btn", use_container_width=True):
                db.update_card_review(card["id"], got_it=False)
                st.session_state.review_index += 1
                st.session_state.card_flipped = False
                st.rerun()

# ─────────────────────────────────────────────────────────────────
# Dashboard section — always shown below the review
# ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Your error patterns")

stats = db.get_error_stats()

if not stats:
    st.info("No corrections recorded yet. Practice a scenario to build your Mistake Deck.")
else:
    # Convert list of dicts to the format st.bar_chart expects
    chart_data = {row["error_type"]: row["count"] for row in stats}
    st.bar_chart(chart_data)

    # Also show a readable summary
    st.markdown("**Breakdown:**")
    for row in stats:
        label = row["error_type"].replace("_", " ").title()
        st.markdown(f"- **{label}**: {row['count']} card{'s' if row['count'] != 1 else ''}")
