#!/usr/bin/env python3
"""Compute per-topic and per-domain counts using cached classifications.

Reads:
 - data/topic_category_cache.json (topic -> {label, domain, note})
 - analytics/event files in data/ (jsonl or json)

Writes:
 - data/topic_counts_ece.json
 - data/topic_counts_robo.json
 - data/topic_counts_all.json
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "topic_category_cache.json"


def load_cache() -> Dict[str, Dict]:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def find_event_files():
    candidates = list(DATA_DIR.glob("*.jsonl")) + list(DATA_DIR.glob("*.json"))
    # also include logs/activity_log.json if present
    log_path = Path(__file__).resolve().parents[1] / 'logs' / 'activity_log.json'
    if log_path.exists():
        candidates.insert(0, log_path)
    return [p for p in candidates if p.name not in ("topic_category_cache.json", "topic_counts_ece.json", "topic_counts_robo.json", "topic_counts_sye.json", "topic_counts_all.json")]


def iter_topics_from_file(p: Path):
    if p.suffix == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            t = j.get("topic") or j.get("topic_id") or j.get("subject")
            if t:
                yield str(t).strip()
    else:
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(j, list):
            for item in j:
                t = item.get("topic") or item.get("topic_id") or item.get("subject")
                if t:
                    yield str(t).strip()


def main():
    cache = load_cache()
    files = find_event_files()
    topic_counter = Counter()
    domain_counter = Counter()
    label_counter = Counter()
    label_map = defaultdict(lambda: {"domain": "unknown", "count": 0})

    for p in files:
        for topic in iter_topics_from_file(p):
            topic_counter[topic] += 1
            meta = cache.get(topic)
            if meta:
                domain = (meta.get("domain") or "unknown").upper()
                label = meta.get("label") or topic
            else:
                domain = "UNKNOWN"
                label = topic

            domain_counter[domain] += 1
            label_counter[label] += 1
            label_map[label]["domain"] = domain
            label_map[label]["count"] += 1

    ece = {k: v for k, v in label_counter.items() if label_map[k]["domain"] == "ECE"}
    robo = {k: v for k, v in label_counter.items() if label_map[k]["domain"] == "ROBO"}
    sye = {k: v for k, v in label_counter.items() if label_map[k]["domain"] == "SYE"}

    out_ece = DATA_DIR / "topic_counts_ece.json"
    out_robo = DATA_DIR / "topic_counts_robo.json"
    out_sye = DATA_DIR / "topic_counts_sye.json"
    out_all = DATA_DIR / "topic_counts_all.json"

    out_ece.write_text(json.dumps({"counts": ece}, indent=2, ensure_ascii=False), encoding="utf-8")
    out_robo.write_text(json.dumps({"counts": robo}, indent=2, ensure_ascii=False), encoding="utf-8")
    out_sye.write_text(json.dumps({"counts": sye}, indent=2, ensure_ascii=False), encoding="utf-8")
    out_all.write_text(json.dumps({"domain_counts": domain_counter, "label_counts": label_counter}, default=int, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Wrote:", out_ece)
    print("Wrote:", out_robo)
    print("Wrote:", out_sye)
    print("Wrote:", out_all)


if __name__ == "__main__":
    main()
