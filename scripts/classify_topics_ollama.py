#!/usr/bin/env python3
"""
Batch classify topic strings into ECE/ROBO labels using Ollama `qwen3:4b` when available.
Falls back to a simple keyword-based classifier when Ollama is not installed.

Outputs cache to `data/topic_category_cache.json`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "topic_category_cache.json"

ECE_LABELS = [
    "Electrical Fundamentals",
    "Circuit Analysis",
    "Passive Components",
    "Electromagnetism & AC Systems",
    "Electrical Machines, Relays and Switches",
    "Semiconductor Devices and applications",
    "Digital Electronics",
    "Instrumentation & Measurement",
    "Computer Engineering Basics",
    "Electronics Communication Basics",
    "Fabrication & Practical Skills",
    "Simulation & Software Tools",
]

ROBO_LABELS = [
    "Electrical/electronics Fundamentals",
    "Sensors",
    "Actuators",
    "Logic & Relay-Based Control",
    "Fluid Power Systems",
    "Control & Automation Systems",
    "PLC & Industrial Automation",
    "Robotics Fundamentals",
    "System Integration, Design, and Control Implementation",
    "Engineering Practice & Case Studies",
]

SYE_LABELS = [
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
    'Applications of Systems Engineering',
]


def load_events(path: Path):
    # Look for common analytics files in data/ and logs/
    candidates = [
        Path(__file__).resolve().parents[1] / 'logs' / 'activity_log.json',
        DATA_DIR / "analytics_events.jsonl",
        DATA_DIR / "analytics_events_normalized.jsonl",
        DATA_DIR / "analytics_events.json",
        DATA_DIR / "events.jsonl",
    ]
    if path:
        candidates.insert(0, Path(path))

    topics = set()
    for p in candidates:
        try:
            if not p.exists():
                continue
            if p.suffix == ".jsonl":
                with p.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        try:
                            j = json.loads(line)
                        except Exception:
                            continue
                        t = j.get("topic") or j.get("topic_id") or j.get("subject")
                        if t:
                            topics.add(str(t).strip())
            else:
                text = p.read_text(encoding="utf-8")
                try:
                    j = json.loads(text)
                except Exception:
                    continue
                if isinstance(j, list):
                    for item in j:
                        t = item.get("topic") or item.get("topic_id") or item.get("subject")
                        if t:
                            topics.add(str(t).strip())
                elif isinstance(j, dict):
                    # single object
                    t = j.get("topic") or j.get("topic_id") or j.get("subject")
                    if t:
                        topics.add(str(t).strip())
        except Exception:
            continue
    return sorted([t for t in topics if t])


def ollama_classify(topic: str) -> Dict:
    """Call ollama qwen3:4b and return a JSON dict with label/domain/note.

    This function attempts to call the local `ollama` binary. If it fails,
    an Exception is raised by the caller to allow fallback.
    """
    prompt = (
        "You are a taxonomy classifier. Map the input topic exactly to one label from the provided lists.\n"
        "ECE labels:\n" + ", ".join(ECE_LABELS) + "\n"
        "ROBO labels:\n" + ", ".join(ROBO_LABELS) + "\n"
        "If the topic is clearly ECE pick one ECE label; if clearly ROBO pick one ROBO label."
        " If ambiguous, pick best-fit and set domain to 'ambiguous'.\n"
        "Respond with JSON ONLY: {\"label\":..., \"domain\":..., \"note\":...}\n"
        f"Topic: '{topic}'\n"
    )

    # Use ollama run with prompt on stdin
    try:
        p = subprocess.run(["ollama", "run", "qwen3:4b"], input=prompt.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        out = p.stdout.decode("utf-8").strip()
        # sometimes model prints text; try to extract JSON substring
        if not out:
            out = p.stderr.decode("utf-8").strip()
        # Heuristic: find first { .. } in output
        start = out.find("{")
        end = out.rfind("}")
        if start != -1 and end != -1:
            js = out[start:end+1]
            return json.loads(js)
        # If not JSON, fallback to simple parse
        return {"label": out[:80], "domain": "ambiguous", "note": out[:200]}
    except FileNotFoundError:
        raise


def simple_keyword_classifier(topic: str) -> Dict:
    t = topic.lower()
    # ECE keywords
    ece_map = {
        "circuit": "Circuit Analysis",
        "ohm": "Circuit Analysis",
        "resistor": "Passive Components",
        "capacitor": "Passive Components",
        "inductor": "Passive Components",
        "magnet": "Electromagnetism & AC Systems",
        "ac": "Electromagnetism & AC Systems",
        "machine": "Electrical Machines, Relays and Switches",
        "relay": "Electrical Machines, Relays and Switches",
        "diode": "Semiconductor Devices and applications",
        "transistor": "Semiconductor Devices and applications",
        "digital": "Digital Electronics",
        "adc": "Instrumentation & Measurement",
        "dac": "Instrumentation & Measurement",
        "communication": "Electronics Communication Basics",
        "fabrication": "Fabrication & Practical Skills",
        "simulation": "Simulation & Software Tools",
        "software": "Simulation & Software Tools",
    }
    for k, v in ece_map.items():
        if k in t:
            return {"label": v, "domain": "ECE", "note": f"keyword:{k}"}

    robo_map = {
        "sensor": "Sensors",
        "encoder": "Sensors",
        "actuator": "Actuators",
        "motor": "Actuators",
        "plc": "PLC & Industrial Automation",
        "control": "Control & Automation Systems",
        "pid": "Control & Automation Systems",
        "hydraulic": "Fluid Power Systems",
        "pneumatic": "Fluid Power Systems",
        "robot": "Robotics Fundamentals",
        "integration": "System Integration, Design, and Control Implementation",
        "case study": "Engineering Practice & Case Studies",
    }
    for k, v in robo_map.items():
        if k in t:
            return {"label": v, "domain": "ROBO", "note": f"keyword:{k}"}

    # SYE keywords
    sye_map = {
        'system': 'Systems Engineering Fundamentals',
        'systems': 'Systems Engineering Fundamentals',
        'systems engineering': 'Introduction to Systems Engineering',
        'requirement': 'Requirements Engineering',
        'requirements': 'Requirements Engineering',
        'traceability': 'Requirements Engineering',
        'model': 'Systems Modeling Fundamentals',
        'modeling': 'Systems Modeling Fundamentals',
        'optimization': 'Decision Analysis & Optimization',
        'operations research': 'Operations Research Techniques',
        'decision': 'Decision Analysis & Optimization',
        'case study': 'Case Studies & Group Projects',
        'communication': 'Engineering Communication',
    }
    for k, v in sye_map.items():
        if k in t:
            return {"label": v, "domain": "SYE", "note": f"keyword:{k}"}

    # default ambiguous
    return {"label": topic, "domain": "ambiguous", "note": "no_keyword_match"}


def main(argv):
    path = None
    if len(argv) >= 2:
        path = argv[1]

    topics = load_events(Path(path) if path else None)
    if not topics:
        print("No topics found in data files. Exiting.")
        return

    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    else:
        cache = {}

    for topic in topics:
        if topic in cache:
            continue
        print("Classifying:", topic)
        # Try Ollama first
        try:
            res = ollama_classify(topic)
            # normalize fields
            label = res.get("label") if isinstance(res, dict) else str(res)
            domain = res.get("domain") if isinstance(res, dict) else "ambiguous"
            note = res.get("note") if isinstance(res, dict) else ""
            cache[topic] = {"label": label, "domain": domain, "note": note}
        except Exception:
            # fallback
            cache[topic] = simple_keyword_classifier(topic)

    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Wrote cache to", CACHE_FILE)


if __name__ == "__main__":
    main(sys.argv)
