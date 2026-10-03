import json
import re

import requests

from core.prompts import build_system_prompt, build_word_lookup_prompt

MODEL = "gemma2:2b"
OLLAMA_BASE_URL = "http://localhost:11434"

FALLBACK_RESPONSE = {
    "reply": "Entschuldigung, ich verstehe nicht. Kannst du das wiederholen?",
    "correction": {
        "original": "",
        "corrected": "",
        "reason": "(Could not parse model response — no correction available)",
        "error_type": "none",
    },
    "goals_completed": [],
    "hint": "Kannst du das wiederholen?",
    "hint_translation": "Can you repeat that?",
}

_WORD_FALLBACK = {
    "meaning": "Could not look up word.",
    "gender": "",
    "example_de": "",
    "example_en": "",
}

_RETRY_NUDGE = (
    "Your previous response was not valid JSON. "
    "Return ONLY this JSON object with no other text, no markdown fences:\n"
    '{"reply":"...","correction":{"original":"...","corrected":"...","reason":"...","error_type":"none"},'
    '"goals_completed":[],"hint":"...","hint_translation":"..."}'
)

_WORD_RETRY_NUDGE = (
    "Your previous response was not valid JSON. "
    "Return ONLY this JSON object with no other text, no markdown fences:\n"
    '{"meaning":"...","gender":"...","example_de":"...","example_en":"..."}'
)


def check_ollama_running() -> bool:
    """Return True if the Ollama server is reachable at localhost:11434."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _call_ollama_api(messages: list[dict], system_prompt: str) -> str:
    """
    Low-level call to Ollama's /api/chat endpoint via requests.
    Returns the assistant's text content string.
    Raises RuntimeError on HTTP error.
    """
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
        )
    data = resp.json()
    return data["message"]["content"]


def call_llm_chat(messages: list[dict], system_prompt: str) -> str:
    """
    Send a chat request to the Ollama model and return the assistant's reply text.

    Tries the `ollama` Python package first; falls back to direct HTTP if the
    package is unavailable or raises an unexpected error.

    Raises
    ------
    RuntimeError
        If Ollama is not running.
    """
    if not check_ollama_running():
        raise RuntimeError(
            "Ollama is not running. Please start it with: ollama serve"
        )

    try:
        import ollama  # optional fast-path via official package

        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = ollama.chat(model=MODEL, messages=full_messages, stream=False)
        # ollama >= 0.2 returns a ChatResponse (Pydantic model), not a plain dict.
        # Support both attribute-style and dict-style access.
        try:
            return response.message.content
        except AttributeError:
            return response["message"]["content"]
    except ImportError:
        # Fall back to direct HTTP requests
        return _call_ollama_api(messages, system_prompt)
    except Exception:
        # Unexpected package error — fall back to HTTP
        return _call_ollama_api(messages, system_prompt)


def parse_scenario_response(raw: str) -> dict:
    """
    Strip markdown code fences then parse JSON.

    Raises json.JSONDecodeError if the result is not valid JSON.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def get_scenario_reply(
    profile: dict,
    scenario: dict,
    completed_goals: list[int],
    chat_history: list[dict],
    user_message: str,
) -> dict:
    """
    Get the AI character's reply for a scenario chat turn.

    Builds the system prompt, appends the user message to the history, calls the
    model, parses the JSON response. Retries once with a nudge on parse failure.
    Returns FALLBACK_RESPONSE if both attempts fail.

    Parameters
    ----------
    profile : dict
        User profile.
    scenario : dict
        Active scenario dict.
    completed_goals : list[int]
        Indices of already-completed goals.
    chat_history : list[dict]
        Prior turns as [{"role": "user"|"assistant", "content": "..."}, ...].
    user_message : str
        The user's latest message.
    """
    if not check_ollama_running():
        raise RuntimeError(
            "Ollama is not running. Please start it with: ollama serve"
        )

    system_prompt = build_system_prompt(profile, scenario, completed_goals)
    messages = chat_history + [{"role": "user", "content": user_message}]

    # First attempt
    try:
        raw = call_llm_chat(messages, system_prompt)
        return parse_scenario_response(raw)
    except json.JSONDecodeError:
        pass

    # Retry with nudge
    try:
        messages_with_nudge = messages + [
            {"role": "user", "content": _RETRY_NUDGE}
        ]
        raw = call_llm_chat(messages_with_nudge, system_prompt)
        return parse_scenario_response(raw)
    except (json.JSONDecodeError, Exception):
        pass

    # Both attempts failed — return safe fallback
    fallback = dict(FALLBACK_RESPONSE)
    fallback["correction"] = dict(FALLBACK_RESPONSE["correction"])
    fallback["correction"]["original"] = user_message
    fallback["correction"]["corrected"] = user_message
    return fallback


def get_word_lookup(word: str) -> dict:
    """
    Look up a German word or phrase using the Words from Life feature.

    Returns a dict with keys: meaning, gender, example_de, example_en.
    Falls back to _WORD_FALLBACK if the model returns unparseable output.
    """
    if not check_ollama_running():
        raise RuntimeError(
            "Ollama is not running. Please start it with: ollama serve"
        )

    prompt = build_word_lookup_prompt(word)
    messages = [{"role": "user", "content": prompt}]

    # First attempt
    try:
        raw = call_llm_chat(messages, "")
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE
        )
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Retry with nudge
    try:
        messages_with_nudge = messages + [
            {"role": "user", "content": _WORD_RETRY_NUDGE}
        ]
        raw = call_llm_chat(messages_with_nudge, "")
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE
        )
        return json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        pass

    return dict(_WORD_FALLBACK)
