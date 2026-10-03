# Implementation Plan — Deutschfreund

## Environment facts (discovered during exploration)

- Workspace: `/Users/family/Documents/Deushchat` — currently empty
- Python: 3.14.7 at `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`
- Streamlit: 1.64.0 already installed
- SQLite: stdlib (3.50.4) — no extra install needed
- Ollama binary: **not installed** — must be installed in step 1
- `ollama` Python package: **not installed** — must be pip-installed in step 1
- Ollama API: `http://localhost:11434` — standard endpoint, used via `requests` as a fallback if the `ollama` package API changes
- Model: `gemma2:2b` — must be pulled after Ollama is installed
- All DB calls: parameterized queries (sqlite3 `?` placeholders)
- All imports: absolute from project root (e.g. `from core.db import …`), run with `streamlit run app.py` from `/Users/family/Documents/Deushchat`

---

## File inventory — every file to create

```
/Users/family/Documents/Deushchat/
  requirements.txt          # pinned dependencies
  app.py                    # entry point: onboarding or welcome-back home page
  pages/
    1_Scenarios.py          # scenario grid + roleplay chat
    2_Mistake_Deck.py       # flashcard review + error dashboard
    3_Words_from_Life.py    # quick word lookup + personal vocab list
  core/
    __init__.py             # empty, makes core a package
    db.py                   # all SQLite setup and CRUD operations
    llm.py                  # Ollama calls, JSON parsing, retry logic
    prompts.py              # system-prompt builder (level + scenario + goals)
  data/
    __init__.py             # empty, makes data a package
    scenarios.py            # 8 scenario dicts as Python data
  README.md                 # setup instructions + how to run
```

---

## Inter-file dependency order

```
requirements.txt            (no deps)
core/__init__.py            (no deps)
data/__init__.py            (no deps)
data/scenarios.py           (no deps)
core/db.py                  (stdlib only: sqlite3, datetime, pathlib)
core/prompts.py             (imports data/scenarios.py for type hints only)
core/llm.py                 (imports core/prompts.py; uses requests or ollama package)
app.py                      (imports core/db.py)
pages/1_Scenarios.py        (imports core/db.py, core/llm.py, data/scenarios.py)
pages/2_Mistake_Deck.py     (imports core/db.py)
pages/3_Words_from_Life.py  (imports core/db.py, core/llm.py)
```

**Rule:** always implement in the order above — nothing imports a file that does not yet exist.

---

## Step 1 — Bootstrap: requirements.txt + install Ollama

**What to do:**
Create `requirements.txt` with pinned versions. Install Ollama (macOS) and pull `gemma2:2b`. Install the `ollama` Python package.

**Files to create:**
- `requirements.txt`

**Content of requirements.txt:**
```
streamlit>=1.32.0
ollama>=0.1.8
requests>=2.31.0
```

**Shell commands (run once, not part of the app code):**
```bash
# Install Ollama on macOS
curl -fsSL https://ollama.com/install.sh | sh
# OR: brew install ollama

# Start Ollama server (keep running in background)
ollama serve &

# Pull the model
ollama pull gemma2:2b

# Install Python dependencies
pip3 install -r requirements.txt
```

**Verify:** `ollama run gemma2:2b "Hallo"` returns German text. `python3 -c "import ollama; print('ok')"` prints ok.

---

## Step 2 — Database layer: core/db.py

**What to do:**
Create the SQLite module. On import it does nothing (no side effects). Call `get_or_create_db()` explicitly to initialise. DB file lives at `~/.deutschfreund/deutschfreund.db` (user home, so it survives `rm -rf` of the project dir and is writable without root).

**Files to create:**
- `core/__init__.py` — empty
- `core/db.py`

**Schema (three tables):**

```sql
CREATE TABLE IF NOT EXISTS profile (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    level       TEXT    NOT NULL,   -- 'A0'|'A1'|'A2'|'B1'
    city        TEXT,
    goal        TEXT    NOT NULL,   -- 'daily_life'|'university'|'both'
    created_at  TEXT    NOT NULL    -- ISO-8601
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY,
    session_id      TEXT    NOT NULL,
    scenario_id     TEXT    NOT NULL,
    role            TEXT    NOT NULL,   -- 'user'|'assistant'
    content         TEXT    NOT NULL,
    correction_json TEXT,               -- NULL for assistant turns
    timestamp       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id              INTEGER PRIMARY KEY,
    front           TEXT    NOT NULL,   -- wrong sentence (or word)
    back            TEXT    NOT NULL,   -- corrected sentence + explanation
    error_type      TEXT    NOT NULL,
    source_scenario TEXT,
    ease            REAL    NOT NULL DEFAULT 2.5,
    interval_days   INTEGER NOT NULL DEFAULT 1,
    next_review     TEXT    NOT NULL,   -- ISO-8601 date
    created_at      TEXT    NOT NULL
);
```

**Functions to implement (all use parameterized `?` placeholders):**
- `get_or_create_db() -> sqlite3.Connection` — opens/creates DB, runs CREATE TABLE IF NOT EXISTS, returns connection
- `save_profile(name, level, city, goal) -> None`
- `get_profile() -> dict | None` — returns first row as dict or None
- `save_message(session_id, scenario_id, role, content, correction_json=None) -> None`
- `get_messages_for_session(session_id) -> list[dict]`
- `save_card(front, back, error_type, source_scenario=None) -> None` — sets ease=2.5, interval_days=1, next_review=today
- `get_due_cards() -> list[dict]` — WHERE next_review <= date.today()
- `update_card_review(card_id, got_it: bool) -> None` — SM-2 lite (see below)
- `get_error_stats() -> list[dict]` — GROUP BY error_type ORDER BY count DESC
- `save_word(word, meaning, gender, example_de, example_en) -> None` — saves as card with error_type='vocabulary'
- `get_all_words() -> list[dict]` — all cards with error_type='vocabulary', ORDER BY created_at DESC

**Connection strategy:** open a new connection per function call, close after. Do not cache connections in module globals (Streamlit reruns the script on every interaction; a cached global connection can go stale across threads). Use `with sqlite3.connect(DB_PATH) as conn:` pattern.

**Verify:** `python3 -c "from core.db import get_or_create_db; conn = get_or_create_db(); print('DB ok')"` from the project root.

---

## Step 3 — Scenario data: data/scenarios.py

**What to do:**
Define `SCENARIOS` as a list of 8 dicts. This is pure data — no imports, no side effects.

**Files to create:**
- `data/__init__.py` — empty
- `data/scenarios.py`

**Each scenario dict shape:**
```python
{
    "id":             "bank",             # snake_case unique key
    "name":           "Bank",
    "emoji":          "🏦",
    "difficulty":     "A1",               # difficulty badge text
    "setup_en":       "You're at the bank...",   # English setup card
    "goals":          ["Greet the clerk", "Ask to open an account", "Spell your name", "Say goodbye"],
    "character_name": "Herr Müller",
    "character_role": "bank teller",
}
```

**Eight scenarios:**
1. `bank` 🏦 — open a student account (difficulty: A1)
2. `visa_office` 🏛️ — Anmeldung / register address (difficulty: A2)
3. `apartment` 🏠 — ask about rent and contract (difficulty: A2)
4. `supermarket` 🛒 — find items, ask price, pay (difficulty: A0)
5. `mensa` 🍽️ — order food, ask what's in it (difficulty: A0)
6. `doctor` 🏥 — describe a simple symptom (difficulty: A1)
7. `professor` 📚 — ask about an assignment (difficulty: B1)
8. `friends` 🤝 — introduce yourself at orientation (difficulty: A0)

**Verify:** `python3 -c "from data.scenarios import SCENARIOS; print(len(SCENARIOS), 'scenarios')"` prints `8 scenarios`.

---

## Step 4 — Prompt builder: core/prompts.py

**What to do:**
Build the system prompt string from profile + scenario + goals state. No LLM calls here — pure string construction.

**Files to create:**
- `core/prompts.py`

**Functions:**
- `build_system_prompt(profile: dict, scenario: dict, completed_goals: list[int]) -> str`

**What the prompt must instruct the model (A0 level):**
```
You are {character_name}, a {character_role}. You are speaking with {name}, a complete beginner
(level A0) learning German. Their goal: {goal}.

LANGUAGE RULES — follow these exactly:
- Speak ONLY in German.
- Use only the 1000 most common German words.
- Keep every sentence under 8 words.
- Use present tense only (Präsens). Never use Konjunktiv or Plusquamperfekt.
- If the student seems confused, repeat your last sentence more slowly or rephrase it.

SCENARIO: {setup_en}
GOALS STILL PENDING: {pending_goals_list}

OUTPUT FORMAT — return ONLY valid JSON, no markdown, no extra text:
{
  "reply": "...",
  "correction": {
    "original": "...",
    "corrected": "...",
    "reason": "...",
    "error_type": "word_order|gender|verb_conjugation|case|vocabulary|none"
  },
  "goals_completed": [...],
  "hint": "...",
  "hint_translation": "..."
}

If the student's message has no errors, set correction.error_type to "none" and
correction.corrected to the same text as correction.original.
goals_completed must list the indices (0-based) of goals the student's message fulfils.
hint is a suggested German reply the student could send next.
hint_translation is the English translation of YOUR reply field above.
```

Also implement:
- `build_word_lookup_prompt(word: str) -> str` — for Words from Life; expects JSON: `{"meaning": "", "gender": "", "example_de": "", "example_en": ""}`

**Verify:** `python3 -c "from core.prompts import build_system_prompt; print('prompts ok')"` from project root.

---

## Step 5 — LLM layer: core/llm.py

**What to do:**
Wrap Ollama calls, parse JSON, implement retry + graceful fallback.

**Files to create:**
- `core/llm.py`

**Implementation decisions:**
- Use the `ollama` Python package's `ollama.chat()` (synchronous). If the package is unavailable, fall back to `requests.post("http://localhost:11434/api/chat", ...)`.
- All calls use `model="gemma2:2b"`.
- `stream=False` so we get the full response before parsing.

**Functions:**

```python
def call_llm_chat(messages: list[dict], system_prompt: str) -> str:
    """Raw call; returns the model's text response string. Raises RuntimeError if Ollama is down."""

def parse_scenario_response(raw: str) -> dict:
    """
    Strip markdown fences (```json ... ``` or ``` ... ```), then json.loads().
    On failure raises json.JSONDecodeError.
    """

def get_scenario_reply(profile: dict, scenario: dict, completed_goals: list[int],
                        chat_history: list[dict], user_message: str) -> dict:
    """
    1. Build system prompt via prompts.build_system_prompt().
    2. Append user_message to chat_history.
    3. Call call_llm_chat().
    4. Try parse_scenario_response().
    5. On JSONDecodeError: retry ONCE with an extra system nudge:
       "Your last response was not valid JSON. Return ONLY the JSON object, nothing else."
    6. If retry also fails: return FALLBACK_RESPONSE (see below).
    Returns the parsed dict.
    """

def get_word_lookup(word: str) -> dict:
    """
    Calls the model with build_word_lookup_prompt(word).
    Same parse + retry + fallback pattern.
    Fallback: {"meaning": "Could not look up word.", "gender": "", "example_de": "", "example_en": ""}
    """

def check_ollama_running() -> bool:
    """GET http://localhost:11434/ — returns True if 200, False otherwise."""
```

**FALLBACK_RESPONSE** (returned when both attempts fail):
```python
{
    "reply": "Entschuldigung, ich verstehe nicht. Kannst du das wiederholen?",
    "correction": {
        "original": user_message,
        "corrected": user_message,
        "reason": "(Could not parse model response — no correction available)",
        "error_type": "none"
    },
    "goals_completed": [],
    "hint": "Kannst du das wiederholen?",
    "hint_translation": "Can you repeat that?"
}
```

**Retry nudge message** injected as an extra `user` turn before the second attempt:
```
"Your previous response was not valid JSON. Return ONLY this JSON object with no other text, no markdown fences:\n{\"reply\":...,\"correction\":{...},\"goals_completed\":[...],\"hint\":\"...\",\"hint_translation\":\"...\"}"
```

**Ollama-not-running guard:** every public function checks `check_ollama_running()` first and raises `RuntimeError("Ollama is not running. Please start it with: ollama serve")` if False — the UI layer catches this and shows `st.error(...)`.

**Verify:** `python3 -c "from core.llm import check_ollama_running; print('llm module ok')"` from project root (does not require Ollama to be running).

---

## Step 6 — SM-2 spaced repetition logic (inside core/db.py: update_card_review)

**Algorithm — SM-2 "lite" (simplified for two-button rating):**

Map the two buttons to SM-2 quality scores:
- "Got it" → quality = 4
- "Try again" → quality = 1

```python
def update_card_review(card_id: int, got_it: bool) -> None:
    quality = 4 if got_it else 1

    # Fetch current ease and interval
    # ease: float, default 2.5
    # interval_days: int, default 1

    if quality >= 3:
        if interval_days == 1:
            new_interval = 1
        elif interval_days == 2:  # (after first successful review)
            new_interval = 6
        else:
            new_interval = round(interval_days * ease)
        new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    else:
        new_interval = 1      # reset to tomorrow
        new_ease = ease - 0.20

    # Clamp ease to floor of 1.3 (standard SM-2 minimum)
    new_ease = max(1.3, new_ease)

    next_review = (date.today() + timedelta(days=new_interval)).isoformat()

    # UPDATE cards SET ease=?, interval_days=?, next_review=? WHERE id=?
```

**Important edge case:** on first review after creation, `interval_days` is 1. A "Got it" keeps it at 1 (review again tomorrow to confirm). On the second "Got it", it jumps to 6. This matches standard SM-2 initialisation.

---

## Step 7 — Entry point and onboarding: app.py

**What to do:**
Home page with two states — first run (onboarding form) and returning user (welcome-back dashboard).

**Files to create:**
- `app.py`

**Logic:**
```python
# At module top (no side effects on import — Streamlit reruns this every interaction)
db.get_or_create_db()   # idempotent — safe to call every run
profile = db.get_profile()

if profile is None:
    # --- ONBOARDING FORM ---
    st.title("Willkommen! 👋 Let's get you set up.")
    with st.form("onboarding"):
        name  = st.text_input("Your first name")
        level = st.selectbox("Your current German level", ["A0", "A1", "A2", "B1"])
        city  = st.text_input("Target city or university (optional)")
        goal  = st.selectbox("Your main goal", [
                    "Survive daily life in Germany",
                    "Pass university admission",
                    "Both"
                ])
        submitted = st.form_submit_button("Start learning!")
    if submitted and name:
        goal_key = {"Survive daily life in Germany": "daily_life",
                    "Pass university admission": "university",
                    "Both": "both"}[goal]
        db.save_profile(name, level, city, goal_key)
        st.switch_page("pages/1_Scenarios.py")
else:
    # --- WELCOME BACK ---
    stats = {
        "due_today": len(db.get_due_cards()),
        "total_corrections": ... # SELECT COUNT(*) FROM cards
    }
    st.title(f"Hallo, {profile['name']}! 👋")
    st.metric("Cards due for review today", stats["due_today"])
    st.metric("Total corrections saved", stats["total_corrections"])
    # Navigation buttons to the three pages
```

**Verify:** `streamlit run app.py` from project root opens the onboarding form in the browser with no errors.

---

## Step 8 — Scenario chat page: pages/1_Scenarios.py

**What to do:**
Scenario grid, then full chat view with correction panel, goals tracker, and hint button.

**Files to create:**
- `pages/1_Scenarios.py`

**Session state keys used:**
- `st.session_state.active_scenario` — the selected scenario dict or None
- `st.session_state.chat_history` — list of `{role, content, correction}` dicts
- `st.session_state.completed_goals` — list of int indices
- `st.session_state.session_id` — uuid4 string, generated when scenario is picked
- `st.session_state.show_hint` — bool

**Grid view:**
```python
cols = st.columns(4)
for i, scenario in enumerate(SCENARIOS):
    with cols[i % 4]:
        if st.button(f"{scenario['emoji']}\n**{scenario['name']}**\n`{scenario['difficulty']}`", key=scenario['id']):
            st.session_state.active_scenario = scenario
            st.session_state.chat_history = []
            st.session_state.completed_goals = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.show_hint = False
            st.rerun()
```

**Chat view (when active_scenario is set):**
1. Show scenario name + difficulty badge header
2. Show setup card in English (st.info)
3. Show goals list with ✅ / ⬜ based on completed_goals
4. Render chat history using `st.chat_message("user")` / `st.chat_message("assistant")`
   - Under each user message, if `correction` is present and `error_type != "none"`, render the Correction Panel in an `st.expander("📝 Correction", expanded=True)`
5. Hint button (`st.button("💡 Hint")`) — sets `show_hint = True`; if True, show `st.info(hint_text)` with the suggested reply and translation
6. `st.chat_input("Type your German reply…")` — on submit:
   - Guard: `if not llm.check_ollama_running(): st.error("…"); st.stop()`
   - Call `llm.get_scenario_reply(profile, scenario, completed_goals, llm_history, user_input)`
   - Append to session state chat history
   - Merge `goals_completed` into `completed_goals` (deduplicate)
   - If correction.error_type != "none": call `db.save_card(original, corrected + "\n" + reason, error_type, scenario['id'])`
   - Call `db.save_message(session_id, scenario_id, "user", user_input, json.dumps(correction))`
   - Call `db.save_message(session_id, scenario_id, "assistant", reply, None)`
   - `st.rerun()`

**LLM chat history format** passed to `llm.get_scenario_reply`:
```python
[{"role": "user"|"assistant", "content": text_string}, ...]
```
Only include `role` and `content` — no correction dicts in the LLM history.

**Verify:** `streamlit run app.py`, navigate to Scenarios, pick Bank, type "Hallo" — see German reply + correction panel.

---

## Step 9 — Mistake Deck page: pages/2_Mistake_Deck.py

**What to do:**
Flashcard review with SM-2 flip interaction, plus error-type dashboard.

**Files to create:**
- `pages/2_Mistake_Deck.py`

**Session state keys:**
- `st.session_state.review_cards` — list of due card dicts, loaded once per session
- `st.session_state.review_index` — int, current position
- `st.session_state.card_flipped` — bool

**Review flow:**
1. On page load (or when `review_cards` not in state): call `db.get_due_cards()`, shuffle, store in state
2. If no cards due: show `st.success("No cards due today! Come back tomorrow. 🎉")`
3. Show progress: `st.progress(review_index / len(review_cards))`
4. Show current card front with `st.markdown(f"**{card['front']}**")`
5. If not flipped: `st.button("Reveal answer")` → sets `card_flipped = True`, `st.rerun()`
6. If flipped: show card back, then two buttons side by side:
   - `st.button("✅ Got it")` → `db.update_card_review(card_id, got_it=True)`, advance index, reset flipped
   - `st.button("❌ Try again")` → `db.update_card_review(card_id, got_it=False)`, advance index, reset flipped
7. When index >= len(cards): show session summary ("You reviewed N cards. Well done!")

**Dashboard (below review):**
- `st.subheader("Your error pattern")`
- Call `db.get_error_stats()` → render as `st.bar_chart` or a simple `st.dataframe`

**Verify:** After a chat session that produced at least one correction, open Mistake Deck — the card appears and both buttons update the card without crashing.

---

## Step 10 — Words from Life page: pages/3_Words_from_Life.py

**What to do:**
Quick word lookup that auto-saves to the deck.

**Files to create:**
- `pages/3_Words_from_Life.py`

**UI:**
1. `st.text_input("Paste a German word or phrase you encountered:")` with a Submit button
2. On submit:
   - Guard: Ollama check, same pattern as Scenarios
   - Call `llm.get_word_lookup(word)` → returns `{meaning, gender, example_de, example_en}`
   - Display result in `st.card` or `st.info` block
   - Call `db.save_word(word, meaning, gender, example_de, example_en)`
3. `st.subheader("Your vocabulary list")`
4. Call `db.get_all_words()` and render as a table or card list

**Word card display format:**
```
🇩🇪 Hund (der)
Meaning: dog
Example: "Der Hund ist groß." → "The dog is big."
```

**Verify:** Type "Hund" into the input, submit — model returns meaning + example, entry appears in the vocabulary list below.

---

## Step 11 — README.md

**What to do:**
Write setup instructions so the user (or friend) can reproduce the environment from scratch.

**Files to create:**
- `README.md`

**Sections:**
1. Prerequisites: macOS, Python 3.11+, Ollama
2. Install steps:
   ```bash
   # 1. Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   ollama serve &          # start in background
   ollama pull gemma2:2b   # download the model (~1.6 GB)

   # 2. Clone / unzip project and cd into it
   cd /path/to/Deushchat

   # 3. Install Python dependencies
   pip3 install -r requirements.txt

   # 4. Run the app
   streamlit run app.py
   ```
3. Usage overview: brief bullet list of the four pages
4. Troubleshooting: "Ollama not running" error message and fix

---

## JSON schema reference (for LLM output)

### Scenario chat response
```json
{
  "reply":            "German text the AI character says",
  "correction": {
    "original":       "exact text the user wrote",
    "corrected":      "corrected version (same as original if no error)",
    "reason":         "one-line English explanation",
    "error_type":     "word_order|gender|verb_conjugation|case|vocabulary|none"
  },
  "goals_completed":  [0, 2],
  "hint":             "suggested German reply the student could send next",
  "hint_translation": "English translation of the reply field"
}
```

### Word lookup response
```json
{
  "meaning":    "English meaning",
  "gender":     "der|die|das|— (empty string if not a noun)",
  "example_de": "German example sentence",
  "example_en": "English translation of example"
}
```

---

## Retry / fallback strategy (summary)

| Situation | Action |
|-----------|--------|
| JSON parses cleanly | Return parsed dict immediately |
| JSONDecodeError on first parse | Strip fences again (belt-and-suspenders), retry call with nudge message appended |
| JSONDecodeError on retry | Return `FALLBACK_RESPONSE` — app never crashes |
| Ollama not running | `check_ollama_running()` returns False → UI shows `st.error()` and `st.stop()` |
| Ollama returns HTTP 4xx/5xx | `requests.post()` raises → caught, treated same as "not running" |

Fence-stripping regex: `re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)`

---

## SM-2 lite — full algorithm (implemented in db.update_card_review)

```
Input:  card's current (ease, interval_days), button pressed
Output: (new_ease, new_interval, new_next_review_date)

quality = 4 if "Got it" else 1

if quality >= 3:  # correct response
    if interval_days == 1:
        new_interval = 1           # confirm tomorrow
    elif interval_days <= 2:
        new_interval = 6           # jump to 6 days
    else:
        new_interval = round(interval_days * ease)
    new_ease = ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    # For quality=4: new_ease = ease + 0.1 - 1*(0.08 + 1*0.02) = ease + 0.1 - 0.10 = ease (unchanged)
else:  # incorrect
    new_interval = 1               # back to tomorrow
    new_ease = ease - 0.20

new_ease = max(1.3, new_ease)      # SM-2 floor

next_review = date.today() + timedelta(days=new_interval)
```

Note: with quality=4 the ease is mathematically unchanged (ease + 0.1 - 0.10 = ease). This is correct SM-2 behaviour — the "Got it" button represents a confident but not perfect recall.

---

## Build and run commands

```bash
# From /Users/family/Documents/Deushchat
streamlit run app.py
```

Streamlit automatically discovers `pages/` directory and renders the sidebar navigation.

## Test commands (manual, since no test framework is configured)

```bash
# Module-level smoke tests (all from project root)
python3 -c "from core.db import get_or_create_db; get_or_create_db(); print('DB ok')"
python3 -c "from core.prompts import build_system_prompt; print('prompts ok')"
python3 -c "from core.llm import check_ollama_running; print('llm ok')"
python3 -c "from data.scenarios import SCENARIOS; assert len(SCENARIOS)==8; print('scenarios ok')"

# Full integration
streamlit run app.py   # verify in browser: no import errors, onboarding form renders
```

---

## Quality checklist

- [ ] Every DB function uses `?` parameterized queries — no f-string SQL
- [ ] `st.session_state` used for all chat state — no globals
- [ ] `get_or_create_db()` called at the top of `app.py` and each page (idempotent)
- [ ] `check_ollama_running()` called before every LLM call in the UI layer
- [ ] Correction panel only rendered when `error_type != "none"`
- [ ] JSON fallback tested by temporarily passing a bad model name
- [ ] All `core/` and `data/` modules importable with no side effects (no `streamlit` calls at module level)
- [ ] `pages/` filenames prefixed with numbers so Streamlit sidebar order is correct: 1_, 2_, 3_
