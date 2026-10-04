# Mistake Deck enhancement — streak, filter, insights, and card browser

The Mistake Deck was rebuilt from a bare spaced-repetition loop into a full review experience. Seven features were added across two files: `core/db.py` gained six new functions and a new `user_stats` table, and `pages/2_Mistake_Deck.py` was rewritten to wire them into a streak tracker, a progress stats bar, an error-type filter, an improved flip-card review flow, a session summary, an insights panel, and a browsable card list. The approach stays within the existing SQLite/Streamlit stack with no new dependencies.

Watch for: the filter-change reset relies on undocumented Streamlit widget-key write ordering, which could silently break on a Streamlit upgrade (confirmed). `get_card_stats` returns a `total_reviewed_today` field that is never consumed by the page and is named imprecisely (confirmed). `update_streak` is only called at session completion, meaning partial sessions earn no streak credit (confirmed).

**Verdict**: NEEDS_CHANGES

---

## High-level view

All six new `db.py` functions use parameterized queries and the `user_stats` table is created inside `get_or_create_db`. No existing functions were modified.

The filter-change reset compares `prev_filter` (captured before the `st.selectbox` call) against the post-render value. This works because Streamlit writes widget keys to `session_state` during rendering, so `prev_filter` holds the previous run's value at the point of comparison — but this ordering is not a documented guarantee. An `on_change` callback is the correct idiom.

`get_card_stats` returns `total_reviewed_today`, which infers "reviewed today" by counting cards with `next_review > today`. The page calls the function but only reads `total` and `mastered`; `total_reviewed_today` is dead. The field name implies a different semantic than the SQL delivers.

`update_streak` fires only when `review_index >= len(review_cards)`, so a user who reviews cards but closes before finishing the full deck does not get streak credit.

---

<details>
<summary>Issues (3)</summary>

1. **Filter reset sequencing (brittle)** — The `prev_filter` / `selected_filter` comparison depends on Streamlit writing widget keys during rendering, not before. Replace with an `on_change` callback on the selectbox to make the reset deterministic and upgrade-safe.

2. **`total_reviewed_today` unused and misleadingly named** — `get_card_stats` returns this field but the page never reads it. The SQL (`next_review > today`) counts rescheduled cards, not cards reviewed today. Either remove the field or surface it in the UI with an accurate label.

3. **Partial session earns no streak credit** — `update_streak()` is gated on completing every due card. A user who reviews half the deck and closes the tab gets no credit. Move the streak update to trigger on the first card review of the day instead.

</details>

<details>
<summary>Details</summary>

### Filter-change deck reset

The reset block reads `prev_filter = st.session_state.get("selected_filter", "All types")` before the `st.selectbox(..., key="selected_filter")` call. Streamlit writes widget keys to `session_state` during rendering, so `prev_filter` captures the previous run's value and the comparison works. The risk is that this ordering is not documented. An `on_change` callback removes the dependency:

```python
def _reset_deck():
    for key in ("review_cards", "review_index", "card_flipped"):
        st.session_state.pop(key, None)

st.selectbox("Filter by error type", options=filter_options,
             key="selected_filter", on_change=_reset_deck)
```

### `get_card_stats` — unused field

```python
stats = db.get_card_stats()
col1.metric("📚 Total cards", stats["total"])
col2.metric("🏆 Mastered", stats["mastered"])
col3.metric("✅ Session accuracy", accuracy_str)   # accuracy_str comes from session_state, not stats
```

`stats["total_reviewed_today"]` is never referenced. The SQL counts `next_review > today` — cards already rescheduled into the future — not a "reviewed today" count in the intuitive sense. If surfaced in the UI it should be labeled "rescheduled today" or the logic should change to track a real review timestamp.

</details>

---

<details>
<summary>File map</summary>

- `core/db.py` — Six new functions added (`get_all_cards`, `get_due_cards_by_type`, `get_due_counts_by_type`, `get_card_stats`, `update_streak`, `get_streak`); `user_stats` table added to `get_or_create_db`; no existing functions modified.
- `pages/2_Mistake_Deck.py` — Full rewrite of the review page with streak display, stats bar, error-type filter, flip-card review, session summary, insights bar chart, and searchable card browser.

Full diff: `git diff main -- core/db.py pages/2_Mistake_Deck.py`

</details>
