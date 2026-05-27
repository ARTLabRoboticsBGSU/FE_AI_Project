import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

from lib.enhanced_usage_logger import load_json_log

def _local_infer_counts(entries):
    # Use the same inference as in home_views.extract_bloom
    def extract_bloom(d):
        try:
            data = d.get('data') or {}
            b = data.get('bloom_level') or data.get('bloom') or data.get('bloom_label')
            if b:
                return str(b)
            text = (data.get('prompt_preview','') + ' ' + data.get('response_preview','')).lower()
            text = text.replace('-', ' ').replace('_', ' ')
            remember_kw = ['remember', 'define', 'what is', 'list', 'name', 'identify', 'state']
            understand_kw = ['explain', 'describe', 'summariz', 'understand', 'interpret', 'compare']
            apply_kw = ['apply', 'use', 'solve', 'calculate', 'implement', 'compute', 'demonstrat']
            analyze_kw = ['analy', 'compare', 'differentiat', 'distinguish', 'diagram', 'break down']
            evaluate_kw = ['evaluate', 'critic', 'assess', 'justify', 'argu', 'select', 'choose']
            create_kw = ['design', 'create', 'construct', 'compose', 'develop', 'formulat']
            def contains_any(txt, kw_list):
                return any(k in txt for k in kw_list)
            if contains_any(text, create_kw):
                return 'Create'
            if contains_any(text, evaluate_kw):
                return 'Evaluate'
            if contains_any(text, analyze_kw):
                return 'Analyze'
            if contains_any(text, apply_kw):
                return 'Apply'
            if contains_any(text, understand_kw):
                return 'Understand'
            if contains_any(text, remember_kw):
                return 'Remember'
            return 'Unknown'
        except Exception:
            return 'Unknown'

    from collections import Counter
    counter = Counter()
    for e in entries:
        counter[extract_bloom(e)] += 1
    return counter


def refresh_bloom_counts(out_dir: Path = Path('data/analytics'), window_days: int = 7, max_items: int = 200) -> Dict[str, Dict[str, int]]:
    """Compute Bloom counts per course and write JSON files.

    Returns a dict mapping course -> counts dict.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(__file__).parent.parent / 'logs' / 'activity_log.json'
    entries = load_json_log(log_path)
    if not entries:
        return {}

    now = datetime.utcnow()
    cutoff = now - timedelta(days=window_days)

    per_course = {}
    for e in entries:
        # skip old entries
        try:
            ts = e.get('timestamp')
            if ts:
                from dateutil import parser
                d = parser.isoparse(ts)
                if d < cutoff:
                    continue
        except Exception:
            pass
        course = (e.get('course') or 'UNKNOWN')
        per_course.setdefault(course, []).append(e)

    ordered_labels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    results = {}
    for course, items in per_course.items():
        subset = items[-max_items:]
        # try to call local LLM classifier if available
        counts = None
        try:
            from lib.chatgeneration import generate_chat_completion
            system_msg = {
                'role': 'system',
                'content': (
                    'You are a helpful assistant that classifies student interactions into Bloom taxonomy categories. '
                    'Given a numbered list of interactions (question and assistant answer), return a JSON object with integer counts for each of the six categories: '
                    'Remember, Understand, Apply, Analyze, Evaluate, Create. ONLY emit valid JSON with a top-level object mapping these six labels to integer counts. '
                    'Do NOT include any other keys.'
                )
            }
            items_msg = []
            for i, e in enumerate(subset, start=1):
                data = e.get('data') or {}
                pq = data.get('prompt_preview','') or ''
                aq = data.get('response_preview','') or ''
                items_msg.append(f"{i}) Q: {pq}\nA: {aq}")
            user_msg = {'role': 'user', 'content': 'Here are recent interactions:\n\n' + '\n\n'.join(items_msg) + '\n\nPlease return counts JSON.'}
            model = 'llama3.2:3b'
            resp_text, _, _ = generate_chat_completion(model, [system_msg, user_msg], temp=0.0, max_num_tokens=512)
            jstart = resp_text.find('{')
            jend = resp_text.rfind('}')
            if jstart != -1 and jend != -1 and jend > jstart:
                parsed = json.loads(resp_text[jstart:jend+1])
                counts = {k: int(parsed.get(k, 0)) for k in ordered_labels}
        except Exception:
            counts = None

        if counts is None:
            # local inference
            from collections import Counter
            c = _local_infer_counts(subset)
            counts = {k: int(c.get(k, 0)) for k in ordered_labels}

        # write to file per course
        out_file = out_dir / f'bloom_counts_{course}.json'
        out_file.write_text(json.dumps(counts))
        results[course] = counts

    return results
