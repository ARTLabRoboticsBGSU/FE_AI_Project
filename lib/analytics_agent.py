"""
Analytics Agent (secondary agent):

- Classify Bloom's taxonomy level for an interaction
- Classify scaffolding type (uses existing scaffolding_classifier)
- Log results asynchronously (uses enhanced_usage_logger)

Designed to be invoked as a background task from the Chat Agent.
"""
from typing import List, Dict, Any
import traceback

from lib import scaffolding_classifier
from lib import chatgeneration
from lib import enhanced_usage_logger as logger
from config import DEFAULT_MODELS


def _build_bloom_prompt(messages: List[Dict[str, Any]]) -> str:
    # Use last user message and last assistant reply
    last_user = None
    last_assistant = None
    for m in reversed(messages):
        if last_assistant is None and m.get('role') == 'assistant':
            last_assistant = m.get('content')
        if last_user is None and m.get('role') == 'user':
            last_user = m.get('content')
        if last_user and last_assistant:
            break

    user_snip = (last_user or '[no user message]')
    assistant_snip = (last_assistant or '[no assistant response]')

    prompt = (
        "You are an educational analyst. Given a single student-LLM exchange, determine the Bloom's Taxonomy level of the student's question.\n\n"
        "Return a JSON object with keys: 'bloom_level' (one of: Remember, Understand, Apply, Analyze, Evaluate, Create),"
        " 'confidence' (0-1), and 'rationale' (1-2 sentences). Reply only with the JSON object.\n\n"
        f"Student prompt:\n{user_snip}\n\nAssistant reply:\n{assistant_snip}\n"
    )
    return prompt


def classify_bloom(messages: List[Dict[str, Any]], model: str | None = None, temperature: float = 0.0) -> Dict[str, Any]:
    if model is None:
        model = DEFAULT_MODELS.get('coding_companion')

    prompt = _build_bloom_prompt(messages)
    system_msg = {"role": "system", "content": "You are a JSON-output classifier. Reply only with JSON."}
    user_msg = {"role": "user", "content": prompt}

    try:
        resp_text, in_toks, out_toks = chatgeneration.generate_chat_completion(model, [system_msg, user_msg], temp=temperature, max_num_tokens=256)
        raw = resp_text.strip()
        import json, re
        try:
            parsed = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {"bloom_level": "Unknown", "confidence": 0.0, "rationale": raw}
        # Normalise keys
        return {
            "bloom_level": parsed.get('bloom_level') or parsed.get('level') or 'Unknown',
            "confidence": float(parsed.get('confidence', 0.0)),
            "rationale": parsed.get('rationale', '') if isinstance(parsed.get('rationale', ''), str) else str(parsed.get('rationale', '')),
            "raw": raw
        }
    except Exception as e:
        return {"bloom_level": "Unknown", "confidence": 0.0, "rationale": f"Error: {e}", "raw": str(e)}


def process_interaction(session_id: str, messages: List[Dict[str, Any]], model: str | None = None):
    """Run analytics (scaffolding classification + Bloom) and log results.

    This function is safe to call from a FastAPI BackgroundTasks worker.
    """
    try:
        # Ensure messages include assistant reply if available
        scaff = scaffolding_classifier.classify_interaction(messages, model=model)
        bloom = classify_bloom(messages, model=model)

        data = {
            "session_id": session_id,
            "scaffolding": {
                "category": scaff.get('category'),
                "confidence": scaff.get('confidence'),
                "rationale": scaff.get('rationale')
            },
            "bloom": {
                "level": bloom.get('bloom_level'),
                "confidence": bloom.get('confidence'),
                "rationale": bloom.get('rationale')
            }
        }

        logger.log_activity(
            activity_type="analytics_classification",
            page="analytics_agent",
            data=data,
            model_used=model
        )

    except Exception:
        # Log the error to the activity log for diagnostics
        err = traceback.format_exc()
        logger.log_activity(activity_type="analytics_error", page="analytics_agent", data={"error": err})
