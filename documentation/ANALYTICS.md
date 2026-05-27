# Analytics & Models Used

This document lists the analytics computations, where they run, and which models or heuristics are used to generate each metric.

Overview of analytics scripts
- `scripts/compute_counts.py` — Aggregates topic counts from event logs and `topic_category_cache.json`. Uses cached classifications produced by `scripts/classify_topics_ollama.py` (or fallback keyword classifier). No external LLM required.
- `scripts/compute_topic_difficulty.py` — Computes difficulty normalized by average time-on-task and log-scaled counts. Purely heuristic (pandas + statistics); no LLM required.
- `scripts/compute_errors.py` — Generates per-course misconception/error files (`data/analytics/error_{COURSE}.json`).
  - Strategy: pair related ai_generation events and ask an LLM to classify subtopic and indicate whether the response shows a misconception.
  - Preferred model: local Ollama `llama3.2:3b` via `lib.chatgeneration.generate_chat_completion` (the code requests this model id). If Ollama not available, code falls back to heuristic keyword matching.
- `scripts/classify_topics_ollama.py` — Classifies topic strings into course labels.
  - Preferred path: call local `ollama run qwen3:4b` (if `ollama` is installed and `qwen3:4b` is pulled). If `ollama` binary is missing, script falls back to a keyword classifier.

Analytics components used by UI
- Misconception / Error Patterns (Instructor Dashboard)
  - Input: `data/analytics/error_{COURSE}.json` constructed by `scripts/compute_errors.py`.
  - Classification source: LLM labeling (default `llama3.2:3b`) + heuristic fallback. Aggregation counts unique students per subtopic.
- Topic Difficulty Heatmap
  - Input: `data/topic_difficulty.json` from `scripts/compute_topic_difficulty.py`.
  - Method: normalized score computed from average time-on-task and log(1+count).
- Bloom's Cognitive Depth Distribution
  - Produced by `lib/analytics_agent.classify_bloom()` which calls `lib/chatgeneration.generate_chat_completion()`.
  - Default model: uses `DEFAULT_MODELS['coding_companion']` (by default `llama3.2:3b`), but will use whichever model is configured in `config.py` or via page settings.
- At-Risk Students
  - Derived heuristically from `logs/activity_log.json` (error rates per student, activity counts) with thresholds in `lib/home_views.py`.

Notes on LLM provider usage
- Local Ollama is used for many offline-capable labeling tasks when available (model ids `llama3.2:3b`, `qwen3:4b` are referenced in code). The runtime HTTP guard (`lib/disable_http.py`) allows only local Ollama by default unless other hosts are whitelisted.
- Hosted providers (OpenAI, Anthropic, Cohere, Groq, HuggingFace) are supported via `lib/chatgeneration.py` if the corresponding API keys are present in the environment and HTTP is permitted.
