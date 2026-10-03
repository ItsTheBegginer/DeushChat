def build_system_prompt(
    profile: dict,
    scenario: dict,
    completed_goals: list[int],
) -> str:
    """
    Build the system prompt that is injected before every LLM call in scenario chat.

    Parameters
    ----------
    profile : dict
        User profile with keys: name, level, goal.
    scenario : dict
        Scenario dict from data/scenarios.py.
    completed_goals : list[int]
        0-based indices of goals already ticked off; these are excluded from the
        pending list so the model knows what still needs to be accomplished.
    """
    name = profile.get("name", "the student")
    level = profile.get("level", "A0")
    goal = profile.get("goal", "daily_life")

    goal_label_map = {
        "daily_life": "survive daily life in Germany",
        "university": "pass university admission",
        "both": "survive daily life in Germany and pass university admission",
    }
    goal_label = goal_label_map.get(goal, goal)

    all_goals: list[str] = scenario.get("goals", [])
    pending_goals = [
        f"{i}. {g}"
        for i, g in enumerate(all_goals)
        if i not in completed_goals
    ]
    pending_goals_text = (
        "\n".join(pending_goals) if pending_goals else "(all goals completed)"
    )

    character_name = scenario.get("character_name", "the character")
    character_role = scenario.get("character_role", "a German speaker")
    setup_en = scenario.get("setup_en", "")

    prompt = f"""You are {character_name}, a {character_role}. You are speaking with {name}, a complete beginner (level {level}) learning German. Their overall goal: {goal_label}.

LANGUAGE RULES — follow these exactly:
- Speak ONLY in German.
- Use only the 1000 most common German words.
- Keep every sentence under 8 words.
- Use present tense only (Präsens). Never use Konjunktiv or Plusquamperfekt.
- If the student seems confused, repeat your last sentence more slowly or rephrase it.

SCENARIO: {setup_en}

GOALS STILL PENDING:
{pending_goals_text}

OUTPUT FORMAT — return ONLY valid JSON, no markdown fences, no extra text:
{{
  "reply": "...",
  "correction": {{
    "original": "...",
    "corrected": "...",
    "reason": "...",
    "error_type": "word_order|gender|verb_conjugation|case|vocabulary|none"
  }},
  "goals_completed": [],
  "hint": "...",
  "hint_translation": "..."
}}

Rules for the JSON fields:
- "reply": your German character's response to the student.
- "correction.original": the exact text the student wrote (copy it verbatim).
- "correction.corrected": the corrected version. If there are no errors, copy the original unchanged.
- "correction.reason": a one-line English explanation of the error. If no error, write "No errors.".
- "correction.error_type": one of word_order, gender, verb_conjugation, case, vocabulary, none.
- "goals_completed": a JSON array of 0-based goal indices fulfilled by the student's current message. Use an empty array [] if none are fulfilled.
- "hint": a suggested German sentence the student could send next.
- "hint_translation": the English translation of your "reply" field (not the hint).

If the student's message has no errors, set correction.error_type to "none".
"""
    return prompt


def build_word_lookup_prompt(word: str) -> str:
    """
    Build the prompt for the Words from Life word/phrase lookup feature.

    Parameters
    ----------
    word : str
        The German word or phrase the student encountered.
    """
    prompt = f"""The user encountered this German word or phrase: "{word}"

Return ONLY valid JSON with no markdown fences, no extra text:
{{
  "meaning": "English meaning of the word or phrase",
  "gender": "der|die|das or empty string if not a noun",
  "example_de": "a short German example sentence using the word",
  "example_en": "English translation of the example sentence"
}}

Rules:
- "meaning": clear, simple English definition.
- "gender": for nouns, give the article (der/die/das). For verbs, phrases, or adjectives, use an empty string "".
- "example_de": a short, natural German sentence (under 10 words).
- "example_en": the English translation of the example sentence.
"""
    return prompt
