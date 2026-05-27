#!/usr/bin/env python3
"""Compute topic difficulty metrics based on time-on-task and counts.

Reads:
 - data/topic_category_cache.json
 - analytics event files in data/ (jsonl or json)

Writes:
 - data/topic_difficulty.json

Difficulty metric (simple): normalized average time per topic scaled by log(1+count).
"""
import json
from pathlib import Path
from statistics import mean, median
from collections import defaultdict
import math

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "topic_category_cache.json"


TIME_KEYS = ["time_spent", "duration_ms", "duration_seconds", "elapsed_seconds", "seconds", "turn_time", "response_time"]


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def find_event_files():
    files = [p for p in DATA_DIR.glob("*.jsonl")] + [p for p in DATA_DIR.glob("*.json")]
    log_path = Path(__file__).resolve().parents[1] / 'logs' / 'activity_log.json'
    if log_path.exists():
        files.insert(0, log_path)
    return files


def extract_time_from_event(ev: dict):
    # Look for known numeric time fields and normalize to seconds
    for k in TIME_KEYS:
        if k in ev and ev[k] is not None:
            try:
                v = float(ev[k])
                # if value is large (likely ms), convert to seconds
                if v > 1e4:
                    return v / 1000.0
                return v
            except Exception:
                continue
    return None


def iter_events_from_file(p: Path):
    text = p.read_text(encoding="utf-8")
    # Try JSON lines first (many logs are newline-delimited JSON objects)
    lines = [l for l in text.splitlines() if l.strip()]
    parsed_any = False
    for line in lines:
        try:
            j = json.loads(line)
            parsed_any = True
            yield j
        except Exception:
            continue
    if parsed_any:
        return

    # Fall back to parsing the whole file as JSON (either a list or single object)
    try:
        j = json.loads(text)
    except Exception:
        return
    if isinstance(j, list):
        for item in j:
            yield item
    elif isinstance(j, dict):
        yield j


def main():
    cache = load_cache()
    files = find_event_files()
    stats = defaultdict(lambda: {"times": [], "count": 0, "domain": "unknown"})
    events = []
    # load all events into memory to compute durations when explicit time fields are missing
    for p in files:
        for ev in iter_events_from_file(p):
            # support cases where iter_events returns a list of events
            ev_items = ev if isinstance(ev, list) else [ev]
            for single in ev_items:
                if not isinstance(single, dict):
                    continue
                # normalize minimal fields
                session_id = single.get('session_id') or single.get('sid') or single.get('session')
                timestamp = single.get('timestamp') or (single.get('data') or {}).get('timestamp')
                prompt = (single.get('data') or {}).get('prompt_preview') or single.get('prompt') or ''
                resp = (single.get('data') or {}).get('response_preview') or single.get('response') or ''
                topic = single.get('topic') or single.get('topic_id') or single.get('subject')
                course = single.get('course') or (single.get('data') or {}).get('course')
                events.append({
                    'raw': single,
                    'session_id': session_id,
                    'timestamp': timestamp,
                    'prompt': prompt,
                    'resp': resp,
                    'topic': topic,
                    'course': course,
                })

    # helper to detect topic from text when not present
    TOPICS_ECE = [
        ('Electrical Fundamentals', ['electrical','fundamental','fundamentals','electrical fundamentals']),
        ('Circuit Analysis', ['circuit','analysis','circuit analysis']),
        ('Passive Components', ['passive','resistor','capacitor','inductor','passive components']),
        ('Electromagnetism & AC Systems', ['electromagnetism','ac','alternating current','ac systems']),
        ('Electrical Machines, Relays and Switches', ['machine','relay','switch','relays','switches','electrical machines']),
        ('Semiconductor Devices and applications', ['semiconductor','diode','transistor','semiconductor devices','applications']),
        ('Digital Electronics', ['digital','logic','boolean','digital electronics']),
        ('Instrumentation & Measurement', ['instrument','measurement','multimeter','oscilloscope','instrumentation','measurement']),
        ('Computer Engineering Basics', ['computer','engineering','computer engineering','basics']),
        ('Electronics Communication Basics', ['communication','electronics','signal','communication basics','electronics communication']),
        ('Fabrication & Practical Skills', ['fabrication','practical','lab','hands-on','fabrication practical']),
        ('Simulation & Software Tools', ['simulation','software','spice','multisim','simulation tools'])
    ]
    TOPICS_ROBO = [
        ('Electrical/electronics Fundamentals', ['electrical','electronics','fundamentals','electrical fundamentals']),
        ('Sensors', ['sensor','sensors','sensing']),
        ('Actuators', ['actuator','actuators','motor','servo']),
        ('Logic & Relay-Based Control', ['logic','relay','relay logic','control']),
        ('Fluid Power Systems', ['fluid','hydraulic','pneumatic','fluid power','pneumatics','hydraulics']),
        ('Control & Automation Systems', ['control','automation','pid','controller','automation systems']),
        ('PLC & Industrial Automation', ['plc','industrial','programmable logic controller','industrial automation']),
        ('Robotics Fundamentals', ['robot','robotics','robotics fundamentals']),
        ('System Integration, Design, and Control Implementation', ['system integration','design','implementation','control implementation']),
        ('Engineering Practice & Case Studies', ['engineering practice','case study','case studies','practice']),
    ]

    TOPICS_SYE = [
        ('Introduction to Systems Engineering', ['system', 'systems', 'introduction', 'systems engineering']),
        ('Systems Engineering Fundamentals', ['systems engineering', 'fundamental', 'fundamentals', 'interdisciplinary']),
        ('Systems Development Life Cycle', ['development', 'life cycle', 'lifecycle', 'verification', 'validation']),
        ('Systems Integration & Design', ['integration', 'architecture', 'interface', 'integration design']),
        ('Requirements Engineering', ['requirement', 'requirements', 'traceability', 'functional requirement']),
        ('Systems Modeling Fundamentals', ['model', 'modeling', 'modeling fundamentals', 'system representation']),
        ('Functional & Behavioral Modeling', ['functional', 'behavioral', 'dfd', 'fsm', 'er diagram']),
        ('Decision Analysis & Optimization', ['decision', 'optimization', 'linear programming', 'utility']),
        ('Operations Research Techniques', ['operations research', 'simplex', 'optimization', 'or techniques']),
        ('Systems Modeling Software', ['core', 'rational', 'modeling software', 'modeling applications']),
        ('Systems Analysis Methodologies', ['analysis', 'methodology', 'evaluation', 'analytical']),
        ('Case Studies & Group Projects', ['case study', 'case studies', 'group project', 'team project']),
        ('Engineering Communication', ['documentation', 'communication', 'technical documentation']),
        ('Applications of Systems Engineering', ['application', 'applications', 'manufacturing', 'service systems']),
    ]

    def detect_topic_from_text(txt, course_hint=None):
        t = (txt or '').lower()
        ch = (course_hint or '').upper()
        if ch == 'ECE':
            topics = TOPICS_ECE
        elif ch == 'ROBO':
            topics = TOPICS_ROBO
        elif ch == 'SYE':
            topics = TOPICS_SYE
        else:
            topics = TOPICS_ECE + TOPICS_ROBO + TOPICS_SYE
        for name, kws in topics:
            for k in kws:
                if k in t:
                    return name
        return 'Other'

    # attach resolved topic and parsed timestamp
    for e in events:
        if not e['topic']:
            e['topic'] = detect_topic_from_text(e['prompt'] + ' ' + e['resp'], e['course'])
        try:
            e['ts'] = None if e['timestamp'] is None else (float(e['timestamp']) if isinstance(e['timestamp'], (int, float)) else e['timestamp'])
        except Exception:
            e['ts'] = e['timestamp']

    # convert timestamp strings to pandas timestamps if possible
    import pandas as pd
    for e in events:
        try:
            e['ts'] = pd.to_datetime(e['ts'], utc=True)
        except Exception:
            e['ts'] = pd.NaT

    # compute durations per (session_id, topic) by sorting by ts and taking delta to next
    by_session_topic = defaultdict(list)
    for e in events:
        key = (e['session_id'] or 'unknown', e['topic'])
        by_session_topic[key].append(e)

    for key, evs in by_session_topic.items():
        evs_sorted = sorted(evs, key=lambda x: x['ts'] if x['ts'] is not None else pd.Timestamp.min)
        for i in range(len(evs_sorted)):
            cur = evs_sorted[i]
            nxt = evs_sorted[i+1] if i+1 < len(evs_sorted) else None
            duration = None
            if nxt and pd.notnull(cur['ts']) and pd.notnull(nxt['ts']):
                delta = (nxt['ts'] - cur['ts']).total_seconds()
                if delta > 0 and delta < 3600:  # ignore huge gaps
                    duration = delta
            # if event has explicit duration fields, prefer those
            explicit = extract_time_from_event(cur['raw'])
            if explicit is not None and explicit > 0:
                stats[cur['topic']]['times'].append(explicit)
            elif duration is not None:
                stats[cur['topic']]['times'].append(duration)
            stats[cur['topic']]['count'] += 1
            meta = cache.get(cur['topic'])
            if meta:
                stats[cur['topic']]['domain'] = meta.get('domain') or stats[cur['topic']]['domain']

    # Compute difficulty score per topic
    out = []
    all_scores = []
    for topic, v in stats.items():
        times = v["times"]
        count = v["count"]
        avg = mean(times) if times else 0.0
        med = median(times) if times else 0.0
        # base score: avg seconds scaled by log(1+count)
        base = avg * math.log1p(count)
        out.append({
            "topic": topic,
            "domain": v.get("domain", "unknown"),
            "count": count,
            "avg_seconds": avg,
            "median_seconds": med,
            "raw_score": base,
        })
        all_scores.append(base)

    # normalize raw_score to 0-1
    if all_scores:
        lo = min(all_scores)
        hi = max(all_scores)
        span = hi - lo if hi != lo else 1.0
        for item in out:
            item["difficulty_norm"] = (item["raw_score"] - lo) / span
    else:
        for item in out:
            item["difficulty_norm"] = 0.0

    out_path = DATA_DIR / "topic_difficulty.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
