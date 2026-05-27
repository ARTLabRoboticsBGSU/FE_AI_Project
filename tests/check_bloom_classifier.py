#!/usr/bin/env python3
"""Quick check script for the Bloom classifier (lib.analytics_agent.classify_bloom).

Run:
    python tests/check_bloom_classifier.py

This script calls `classify_bloom` on a few sample exchanges and prints JSON results.
"""
import json

from lib.analytics_agent import classify_bloom

SAMPLES = [
    # (expected_bloom_level, messages)
    ("Remember", [
        {"role": "user", "content": "What is Ohm's law?"},
        {"role": "assistant", "content": "Ohm's law states that V = I * R, where V is voltage, I is current, and R is resistance."}
    ]),

    ("Understand", [
        {"role": "user", "content": "Explain in simple terms what a resistor does in a circuit."},
        {"role": "assistant", "content": "A resistor limits the flow of electric current and drops voltage according to Ohm's law."}
    ]),

    ("Apply", [
        {"role": "user", "content": "I have a 10Ω resistor and 5V applied — calculate the current."},
        {"role": "assistant", "content": "I = V / R = 5 / 10 = 0.5 A."}
    ]),

    ("Analyze", [
        {"role": "user", "content": "Compare the behavior of a series versus parallel resistor network when one resistor fails."},
        {"role": "assistant", "content": "In series, the circuit opens if a resistor fails (current stops); in parallel, remaining branches still conduct but overall resistance changes."}
    ]),

    ("Evaluate", [
        {"role": "user", "content": "Which sensor placement strategy gives more reliable temperature readings for this experiment and why?"},
        {"role": "assistant", "content": "Placing the sensor in direct contact with the resistor surface and insulating it from drafts provides the most consistent readings because it minimizes environmental noise."}
    ]),

    ("Create", [
        {"role": "user", "content": "Design a simple experiment to measure the temperature coefficient of resistance for this resistor and describe the steps."},
        {"role": "assistant", "content": "Develop a protocol: heat in controlled increments, record resistance at each temp, plot and fit to extract coefficient; include controls and calibration."}
    ])
]


def run_samples():
    for name, messages in SAMPLES:
        print(f"=== Sample: {name} ===")
        try:
            result = classify_bloom(messages)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
        else:
            print(json.dumps(result, indent=2))

            # Validate returned Bloom level
            allowed_levels = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create", "Unknown"}
            level = None
            if isinstance(result, dict):
                # Support different key names used by classifiers
                level = result.get('bloom_level') or result.get('level') or result.get('bloom')
            if not level:
                print("WARN: No bloom level returned by classifier.")
            else:
                if level not in allowed_levels:
                    print(f"WARN: Unexpected bloom level '{level}'. Allowed: {sorted(allowed_levels)}")
                else:
                    print(f"OK: Bloom level '{level}' is valid.")
        print()


if __name__ == "__main__":
    run_samples()
