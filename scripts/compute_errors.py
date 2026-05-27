#!/usr/bin/env python3
"""Generate per-course misconception/error files from activity logs.

Writes `data/analytics/error_{COURSE}.json` with entries like:
  {timestamp, session_id, course, topic, subtopic, prompt, response, misconception}

Strategy:
- Pair consecutive `ai_generation` entries with the same `session_id`.
- For each pair, take the earlier entry's prompt as question and the later entry's response as answer.
- Ask local LLM (via `lib.chatgeneration.generate_chat_completion`) to decide if answer contains a misconception
  and to pick a subtopic from the provided list for the detected topic. Falls back to keyword heuristic.
"""
import json
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / 'logs' / 'activity_log.json'
OUT_DIR = ROOT / 'data' / 'analytics'
OUT_DIR.mkdir(parents=True, exist_ok=True)

ECE_TOPICS = [
    'Electrical Fundamentals', 'Circuit Analysis', 'Passive Components', 'Electromagnetism & AC Systems',
    'Electrical Machines, Relays and Switches', 'Semiconductor Devices and applications', 'Digital Electronics',
    'Instrumentation & Measurement', 'Computer Engineering Basics', 'Electronics Communication Basics',
    'Fabrication & Practical Skills', 'Simulation & Software Tools'
]
ROBO_TOPICS = [
    'Electrical/electronics Fundamentals', 'Sensors', 'Actuators', 'Logic & Relay-Based Control',
    'Fluid Power Systems', 'Control & Automation Systems', 'PLC & Industrial Automation', 'Robotics Fundamentals',
    'System Integration, Design, and Control Implementation', 'Engineering Practice & Case Studies'
]

ECE_SUBTOPICS = {
    'Electrical Fundamentals': ["Ohm’s Law", "Voltage, Current, Resistance", "Metric Units"],
    'Circuit Analysis': ['Series Circuits', 'Parallel Circuits', 'Circuit Behavior & Analysis'],
    'Passive Components': ['Resistors', 'Capacitors', 'Inductors', 'Transformers'],
    'Electromagnetism & AC Systems': ['Electromagnetic Principles', 'AC Circuits', 'Frequency & Waveforms'],
    'Electrical Machines, Relays and Switches': ['DC Motors', 'Relay Circuits and Switches'],
    'Semiconductor Devices and applications': ['Diodes', 'Rectifier Circuits', 'Transistors (BJT)', 'Switching and Amplifier circuit'],
    'Digital Electronics': ['Binary Numbers', 'Logic Gates', 'Basic Digital Logic'],
    'Instrumentation & Measurement': ['Lab Instruments', 'Measurement Techniques', 'Signal Observation'],
    'Computer Engineering Basics': ['Computer System Overview', 'CPU', 'Embedded', 'AI hardware', 'Career Paths'],
    'Electronics Communication Basics': ['Communication Types', 'Modulation/Demodulation techniques'],
    'Fabrication & Practical Skills': ['Soldering', 'Circuit Assembly', 'PCB wiring and Debugging'],
    'Simulation & Software Tools': ['Multisim', 'Circuit Simulation', 'Debugging in Simulation'],
}

ROBO_SUBTOPICS = {
    'Electrical/electronics Fundamentals': ['Ohm’s Law', 'Voltage, Current, Resistance', 'Electronics components'],
    'Sensors': ['Types of Sensors', 'Signal Acquisition', 'Sensor Integration'],
    'Actuators': ['Electrical Actuators', 'Mechanical Actuation', 'Actuator Selection'],
    'Logic & Relay-Based Control': ['Relay Circuits', 'Logic Circuits', 'Basic Control Logic'],
    'Fluid Power Systems': ['Hydraulic Circuits', 'Pneumatic Circuits', 'Electro-Pneumatic/hydraulic circuits'],
    'Control & Automation Systems': ['Open-loop Systems', 'Closed-loop Systems', 'Automation Architecture'],
    'PLC & Industrial Automation': ['PLC Basics', 'Ladder Logic', 'PLC Programming basics'],
    'Robotics Fundamentals': ['Robot Components', 'Robot Programming Basics', 'Industrial Robots'],
    'System Integration, Design, and Control Implementation': ['Sensor-Actuator Integration', 'System Testing', 'Troubleshooting', 'Automation Programming', 'Logic Debugging', 'Control Execution'],
    'Engineering Practice & Case Studies': ['Automation Case Study', 'Mini Project Design', 'System Evaluation'],
}

# SYE (Systems Engineering) topics and subtopics
SYE_TOPICS = [
    'Introduction to Systems Engineering',
    'Systems Engineering Fundamentals',
    'Systems Development Life Cycle',
    'Systems Integration & Design',
    'Requirements Engineering',
    'Systems Modeling Fundamentals',
    'Functional & Behavioral Modeling',
    'Decision Analysis & Optimization',
    'Operations Research Techniques',
    'Systems Modeling Software',
    'Systems Analysis Methodologies',
    'Case Studies & Group Projects',
    'Engineering Communication',
    'Applications of Systems Engineering'
]

SYE_SUBTOPICS = {
    'Introduction to Systems Engineering': ['Systems Thinking', 'System Components', 'Engineering Systems'],
    'Systems Engineering Fundamentals': ['Interdisciplinary Design', 'System Analysis', 'Lifecycle Concepts'],
    'Systems Development Life Cycle': ['Development Phases', 'Maintenance', 'Verification & Validation'],
    'Systems Integration & Design': ['System Architecture', 'Integration', 'Interface Design'],
    'Requirements Engineering': ['Functional Requirements', 'Traceability', 'Requirement Writing'],
    'Systems Modeling Fundamentals': ['Modeling Concepts', 'Model Types', 'System Representation'],
    'Functional & Behavioral Modeling': ['DFDs', 'E-R Diagrams', 'FSMs'],
    'Decision Analysis & Optimization': ['Decision Making', 'Utility Functions', 'Linear Programming'],
    'Operations Research Techniques': ['Simplex Method', 'Optimization', 'Problem Solving'],
    'Systems Modeling Software': ['CORE', 'Rational', 'Modeling Applications'],
    'Systems Analysis Methodologies': ['Process Analysis', 'Evaluation Methods', 'Analytical Techniques'],
    'Case Studies & Group Projects': ['Team Projects', 'Case Studies', 'System Applications'],
    'Engineering Communication': ['Technical Documentation', 'Collaboration', 'Professional Practice'],
    'Applications of Systems Engineering': ['Manufacturing Systems', 'Service Systems', 'Complex Systems'],
}


def load_logs():
    if not LOG_PATH.exists():
        print('No activity_log.json found', file=sys.stderr)
        return []
    try:
        text = LOG_PATH.read_text(encoding='utf-8')
        # file may be newline-delimited JSON
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        entries = [json.loads(l) for l in lines]
        # keep only ai_generation
        entries = [e for e in entries if e.get('activity_type') == 'ai_generation']
        # sort by timestamp
        entries.sort(key=lambda e: e.get('timestamp') or '')
        return entries
    except Exception as e:
        print('Failed to load logs:', e, file=sys.stderr)
        return []


def detect_topic_from_text(text: str, course: str):
    t = (text or '').lower()
    if course == 'ROBO':
        choices = ROBO_TOPICS
    elif course == 'SYE':
        choices = SYE_TOPICS
    else:
        choices = ECE_TOPICS
    for c in choices:
        key = ''.join(ch for ch in c.lower() if ch.isalnum() or ch.isspace())
        for part in key.split():
            if len(part) > 3 and part in t:
                return c
    return None


def classify_with_llm(pairs, sublabels):
    # pairs is list of {'q','a'}; returns list of dict with keys subtopic, misconception
    try:
        from lib.chatgeneration import generate_chat_completion
    except Exception:
        generate_chat_completion = None

    results = []
    if generate_chat_completion:
        model = 'llama3.2:3b'
        # create a single prompt
        system = {'role': 'system', 'content': 'You are a classifier. Return a JSON array of objects {index, subtopic, misconception}.'}
        labels_text = '\n'.join(f'- {s}' for s in sublabels) if sublabels else ''
        user = {'role': 'user', 'content': 'Subtopic labels:\n' + labels_text + '\n\nClassify the following items. For each, return index (1-based), subtopic (one of the labels or Other), and misconception (true/false).\n\n' + '\n\n'.join(f"{i+1}) Q: {p['q'][:400]}\nA: {p['a'][:400]}" for i,p in enumerate(pairs))}
        try:
            resp_text, _, _ = generate_chat_completion(model, [system, user], temp=0.0, max_num_tokens=1024)
            jstart = resp_text.find('[')
            jend = resp_text.rfind(']')
            if jstart != -1 and jend != -1 and jend > jstart:
                arr_text = resp_text[jstart:jend+1]
                parsed = json.loads(arr_text)
                for obj in parsed:
                    results.append({'subtopic': obj.get('subtopic'), 'misconception': bool(obj.get('misconception', False))})
                return results
        except Exception:
            pass

    # fallback heuristic
    for p in pairs:
        text = (p.get('q','') + ' ' + p.get('a','')).lower()
        sub = None
        for s in sublabels:
            # match significant words
            parts = [w for w in s.lower().replace('/', ' ').replace('&', ' ').split() if len(w) > 3]
            if any(part in text for part in parts):
                sub = s
                break
        if not sub and sublabels:
            sub = sublabels[0]
        mis = any(k in text for k in ['incorrect', 'not correct', "that's wrong", 'mistake', 'wrong', 'incorrectly'])
        results.append({'subtopic': sub, 'misconception': bool(mis)})
    return results


def ask_misconception_llm_single(q, a, topic=None):
    """Ask the LLM a direct yes/no if the answer `a` contains a misconception for question `q`.

    Returns True/False or None if unavailable.
    """
    try:
        from lib.chatgeneration import generate_chat_completion
    except Exception:
        return None
    try:
        system = {'role': 'system', 'content': 'You are an educational evaluator. Answer concisely in JSON.'}
        prompt = (
            'Given the student interaction below, answer whether the STUDENT ANSWER contains a factual or conceptual misconception relative to the QUESTION and the topic provided. '
            'Return only valid JSON: {"misconception": true|false, "confidence": 0.0-1.0, "explanation": "short"}.'
        )
        if topic:
            prompt += f" Topic: {topic}."
        prompt += '\n\nQUESTION:\n' + (q or '')[:1000] + '\n\nSTUDENT ANSWER:\n' + (a or '')[:2000]
        user = {'role': 'user', 'content': prompt}
        # prefer deterministic
        resp_text, _, _ = generate_chat_completion('llama3.2:3b', [system, user], temp=0.0, max_num_tokens=256)
        jstart = resp_text.find('{')
        jend = resp_text.rfind('}')
        if jstart != -1 and jend != -1 and jend > jstart:
            obj = json.loads(resp_text[jstart:jend+1])
            return bool(obj.get('misconception'))
    except Exception:
        return None
    return None


def main():
    entries = load_logs()
    if not entries:
        print('No ai_generation entries to process')
        return

    # build QA pairs per session using multiple heuristics to maximize coverage
    out_per_course = {}
    from collections import defaultdict
    by_session = defaultdict(list)
    for e in entries:
        sid = e.get('session_id') or 'NOSESSION'
        by_session[sid].append(e)

    for sid, sess_entries in by_session.items():
        # sort by timestamp
        try:
            sess_entries.sort(key=lambda e: e.get('timestamp') or '')
        except Exception:
            pass

        seen_pairs = set()
        for idx, e in enumerate(sess_entries):
            data = e.get('data') or {}
            prompt = data.get('prompt_preview') or ''
            response = data.get('response_preview') or ''
            course = e.get('course') or 'UNKNOWN'

            # heuristic 1: same-entry Q->A
            if prompt and response:
                q = prompt.strip()
                atext = response.strip()
                key = (q, atext)
                if key not in seen_pairs:
                    topic = data.get('topic') or detect_topic_from_text(q + ' ' + atext, course)
                    entry = {'timestamp': e.get('timestamp'), 'session_id': sid, 'course': course, 'topic': topic or 'Other', 'prompt': q, 'response': atext}
                    out_per_course.setdefault(course, []).append(entry)
                    seen_pairs.add(key)

            # heuristic 2: response in this entry is a question, next entry's prompt is an answer
            if response and response.strip().endswith('?') and idx + 1 < len(sess_entries):
                nxt = sess_entries[idx + 1]
                nxt_data = nxt.get('data') or {}
                nxt_prompt = nxt_data.get('prompt_preview') or ''
                if nxt_prompt:
                    q = response.strip()
                    atext = nxt_prompt.strip()
                    key = (q, atext)
                    if key not in seen_pairs:
                        course2 = nxt.get('course') or course
                        topic = data.get('topic') or nxt_data.get('topic') or detect_topic_from_text(q + ' ' + atext, course2)
                        entry = {'timestamp': e.get('timestamp'), 'session_id': sid, 'course': course2, 'topic': topic or 'Other', 'prompt': q, 'response': atext}
                        out_per_course.setdefault(course2, []).append(entry)
                        seen_pairs.add(key)

            # heuristic 3: if prompt is short/empty but response is long, pair response->next response if available
            if not prompt and response and idx + 1 < len(sess_entries):
                nxt = sess_entries[idx + 1]
                nxt_data = nxt.get('data') or {}
                nxt_response = nxt_data.get('response_preview') or ''
                if nxt_response:
                    q = response.strip()
                    atext = nxt_response.strip()
                    key = (q, atext)
                    if key not in seen_pairs:
                        course2 = nxt.get('course') or course
                        topic = data.get('topic') or nxt_data.get('topic') or detect_topic_from_text(q + ' ' + atext, course2)
                        entry = {'timestamp': e.get('timestamp'), 'session_id': sid, 'course': course2, 'topic': topic or 'Other', 'prompt': q, 'response': atext}
                        out_per_course.setdefault(course2, []).append(entry)
                        seen_pairs.add(key)

    # For each course, classify subtopic and misconception
    for course, items in out_per_course.items():
        course_key = course.upper() if isinstance(course, str) else str(course)
        results = []
        for it in items:
            topic = it.get('topic')
            if course_key == 'ROBO':
                sublabels = ROBO_SUBTOPICS.get(topic, []) if topic in ROBO_SUBTOPICS else []
            elif course_key == 'SYE':
                sublabels = SYE_SUBTOPICS.get(topic, []) if topic in SYE_SUBTOPICS else []
            else:
                sublabels = ECE_SUBTOPICS.get(topic, []) if topic in ECE_SUBTOPICS else []
            # For each single item, we call classifier with one pair
            classified = classify_with_llm([{'q': it.get('prompt'), 'a': it.get('response')}], sublabels)
            res = classified[0] if classified else {'subtopic': (sublabels[0] if sublabels else 'Other'), 'misconception': False}
            # If the result indicates no misconception but the heuristic or batch LLM may be uncertain, ask the LLM a focused yes/no question
            mis_flag = bool(res.get('misconception', False))
            if not mis_flag:
                try:
                    llm_check = ask_misconception_llm_single(it.get('prompt'), it.get('response'), topic=it.get('topic'))
                    if llm_check is True:
                        mis_flag = True
                    elif llm_check is False:
                        mis_flag = False
                except Exception:
                    pass
            out = dict(it)
            out.update({'subtopic': res.get('subtopic'), 'misconception': bool(mis_flag)})
            results.append(out)

        out_path = OUT_DIR / f'error_{course_key}.json'
        try:
            out_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
            print('Wrote', out_path)
        except Exception as e:
            print('Failed to write', out_path, e, file=sys.stderr)


if __name__ == '__main__':
    main()
