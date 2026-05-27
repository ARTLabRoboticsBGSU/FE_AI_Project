"""
Scaffolding classifier using local Ollama model via existing `lib.chatgeneration.generate_chat_completion`.
Exports: classify_interaction(messages, model=None)

The classifier will summarize the last user-assistant exchange and ask the model to choose one of six
categories and provide a short rationale. Returns a dict with keys: category, confidence, rationale.
"""
from typing import List, Dict, Any
import streamlit as st
from lib import chatgeneration
from config import MODELS

# Default Ollama model to use for classification (must exist in config.MODELS)
DEFAULT_OLLAMA_MODEL = None
for m, cfg in MODELS.items():
    if cfg.get("provider") == "ollama":
        DEFAULT_OLLAMA_MODEL = m
        break

if DEFAULT_OLLAMA_MODEL is None:
    DEFAULT_OLLAMA_MODEL = list(MODELS.keys())[0]  # fallback (will raise if not supported)

CATEGORIES = [
    "Conceptual",
    "Procedural",
    "Strategic",
    "Reflective",
    "Affective",
    "Other/None"
]


def _build_prompt(messages: List[Dict[str, Any]]) -> str:
    """Compose a compact prompt that includes the last user message and assistant response.
    messages: list of dicts with keys 'role' and 'content'
    """
    # Find the last user message and the assistant reply that follows
    last_user = None
    last_assistant = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            last_assistant = messages[i].get("content")
            # try to find a preceding user message
            for j in range(i - 1, -1, -1):
                if messages[j].get("role") == "user":
                    last_user = messages[j].get("content")
                    break
            break

    # fallback: use the last two messages if roles not present as expected
    if last_user is None:
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content")
                break
    if last_assistant is None:
        for m in reversed(messages):
            if m.get("role") == "assistant":
                last_assistant = m.get("content")
                break

    user_snip = (last_user[:800] + "...") if last_user and len(last_user) > 800 else (last_user or "[no user message]")
    assistant_snip = (last_assistant[:1200] + "...") if last_assistant and len(last_assistant) > 1200 else (last_assistant or "[no assistant response]")

    prompt = (
        "You are a pedagogical analyst. Given a single student-LLM exchange, classify the student's behavior/need into one of the following six scaffolding categories: "
        "Conceptual, Procedural, Strategic, Reflective, Affective, or Other/None.\n\n"
        "Provide a JSON object with keys: 'category' (one of the six labels), 'confidence' (0-1), and 'rationale' (1-2 sentences explaining why).\n\n"
        "Important: Reply ONLY with the JSON object and nothing else.\n\n"
        "Student prompt:\n" + user_snip + "\n\n"
        "Assistant reply:\n" + assistant_snip + "\n\n"
        "Consider whether the student's follow-up behavior (if any) indicates confusion, procedural error, planning needs, reflective stance, or affective statements (frustration/encouragement). If unsure, use 'Other/None'." 
    )
    return prompt


def classify_interaction(messages: List[Dict[str, Any]], model: str = None, temperature: float = 0.0) -> Dict[str, Any]:
    """Classify a recent student-assistant exchange.

    Args:
        messages: conversation messages (list of dicts with 'role' and 'content')
        model: optional model override (must be in config.MODELS). If None, use local ollama model.

    Returns:
        dict: {'category': str, 'confidence': float, 'rationale': str, 'raw': str}
    """
    if model is None:
        model = DEFAULT_OLLAMA_MODEL

    if model not in MODELS:
        raise ValueError(f"Model {model} not in config.MODELS")

    prompt = _build_prompt(messages)

    # Pass prompt to the chatgeneration.generate_chat_completion as a single system message
    system_message = {"role": "system", "content": "You are a JSON-output classifier. Strictly output JSON."}
    user_message = {"role": "user", "content": prompt}

    try:
        response_text, _, _ = chatgeneration.generate_chat_completion(
            model=model,
            messages=[system_message, user_message],
            temp=temperature,
            max_num_tokens=256
        )
    except Exception as e:
        st.error(f"Scaffolding classifier failed: {e}")
        return {"category": "Other/None", "confidence": 0.0, "rationale": f"Classifier error: {e}", "raw": ""}

    raw = response_text.strip()

    # Attempt to parse JSON from the model output conservatively
    import json
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        # Try to extract JSON substring
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

    if not parsed or 'category' not in parsed:
        return {"category": "Other/None", "confidence": 0.0, "rationale": "Could not parse classifier output.", "raw": raw}

    cat = parsed.get('category')
    conf = parsed.get('confidence', 0.0)
    try:
        conf = float(conf)
    except Exception:
        conf = 0.0

    rationale = parsed.get('rationale', '')

    return {"category": cat, "confidence": conf, "rationale": rationale, "raw": raw}
