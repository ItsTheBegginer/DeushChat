import streamlit as st

from core import db, llm
from core.db import get_or_create_db

st.set_page_config(page_title="Words from Life — Deutschfreund", page_icon="📖", layout="wide")

# Initialise DB (idempotent)
get_or_create_db()

st.title("Words from Life 📝")
st.caption(
    "Encountered a German word in the wild — on a sign, an email, a class slide? "
    "Paste it here and the tutor will explain it, then add it to your deck."
)

# ─────────────────────────────────────────────────────────────────
# Word lookup form
# ─────────────────────────────────────────────────────────────────
with st.form("word_lookup_form", clear_on_submit=True):
    word_input = st.text_input(
        "Paste a German word or phrase you encountered:",
        placeholder="e.g. Ausländerbehörde, Guten Morgen, der Schlüssel",
    )
    submitted = st.form_submit_button("Look it up →")

if submitted and word_input.strip():
    word = word_input.strip()

    # Guard: Ollama must be running
    if not llm.check_ollama_running():
        st.error(
            "⚠️ Ollama is not running. Start it with: `ollama serve`\n\n"
            "Then refresh this page."
        )
        st.stop()

    with st.spinner(f"Looking up **{word}**…"):
        result = llm.get_word_lookup(word)

    meaning = result.get("meaning", "")
    gender = result.get("gender", "")
    example_de = result.get("example_de", "")
    example_en = result.get("example_en", "")

    # Display result card
    # Format:  🇩🇪 Hund (der)
    #          Meaning: dog
    #          Example: 'Der Hund ist groß.' → 'The dog is big.'
    gender_display = f" ({gender})" if gender else ""
    st.markdown("---")
    st.markdown(f"### 🇩🇪 {word}{gender_display}")
    st.markdown(f"**Meaning:** {meaning}")
    if example_de:
        example_line = f"*{example_de}*"
        if example_en:
            example_line += f"  →  *{example_en}*"
        st.markdown(f"**Example:** {example_line}")

    # Save to deck
    db.save_word(word, meaning, gender, example_de, example_en)
    st.success("Added to your deck! ✅")

elif submitted and not word_input.strip():
    st.warning("Please enter a word or phrase before submitting.")

# ─────────────────────────────────────────────────────────────────
# Vocabulary list
# ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Your vocabulary list")

words = db.get_all_words()

if not words:
    st.info("No words added yet. Look up a word above to start building your list.")
else:
    st.caption(f"{len(words)} word{'s' if len(words) != 1 else ''} in your deck")

    for word_card in words:
        front = word_card.get("front", "")
        back = word_card.get("back", "")

        # Parse back field — format written by db.save_word:
        # "(der) dog\n\nExample: "Der Hund ist groß." → "The dog is big.""
        # or just "meaning" when no gender/example
        with st.expander(f"🇩🇪 {front}", expanded=False):
            st.markdown(back)
