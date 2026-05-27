# FE-AI — Technical Documentation (Research-ready)

This document collects technical details suitable for inclusion in a methods section of a research paper. It summarizes architecture, data flows, RAG pipeline, analytics, evaluation protocol, and reproducibility guidance.

## 1. High-level overview
FE-AI is a Streamlit-based dual-interface system:
- Student UI: interactive student-facing tools (Coding Companion, AI Sandbox, Exam Ally, etc.).
- Instructor UI: analytics dashboard for monitoring topic difficulty, misconceptions, Bloom distribution, and at-risk students.

The app combines local retrieval (FAISS), local or hosted LLMs (Ollama or API), and offline analytics scripts.

See the architecture diagram: `documentation/ARCHITECTURE.md` (includes a mermaid diagram).

## 2. Core components and file layout
- Entrypoint: `chatgpt.py` — initialises Streamlit UI, theme, and routes to pages.
- Pages: `pages/*` — Streamlit pages for Student and Instructor flows.
- RAG: `lib/rag.py` — retrieval implementation (FAISS + sentence-transformers; TF‑IDF fallback via scikit-learn).
- Generation: `lib/chatgeneration.py` — unified abstraction for model providers (OpenAI, Anthropic, Cohere, HuggingFace, Groq, Ollama).
- Analytics helpers: `scripts/*` and `lib/analytics_helpers.py` — compute difficulty, counts, and error/misconception derivations.
- Data stores:
  - `logs/activity_log.json` — streaming interaction events.
  - `data/vector_index/<COURSE>/docs.jsonl` and `index.faiss` — RAG corpus and vector index.
  - `data/analytics/*` — per-course analytics outputs (e.g., `error_ECE.json`).

## 3. RAG pipeline (detailed)
- Knowledge base: stored as newline-delimited JSON documents in `data/vector_index/<COURSE>/docs.jsonl`.
- Vector database: FAISS index files located at `data/vector_index/<COURSE>/index.faiss`.
- Embeddings: produced using `sentence-transformers` (local model) via `SentenceTransformer` in `lib/rag.py`.
- Retrieval:
  1. Query text -> embedding (SentenceTransformer).
  2. FAISS similarity search -> candidate document(s).
  3. Optional similarity thresholding and top-K selection (project uses top-1 in coding companion pages).
- TF‑IDF fallback: when embeddings or sentence-transformers unavailable, `lib/rag.py` builds a TF‑IDF matrix (sklearn) and ranks documents by cosine similarity.

Files of interest: `lib/rag.py`, `scripts/build_rag.py`, `data/vector_index/*`.

## 4. Analytics pipeline and models
- Topic classification: `scripts/classify_topics_ollama.py` — prefers local Ollama model `qwen3:4b` (via `ollama run`) to map topic strings to course labels; falls back to keyword classifier.
- Misconception detection: `scripts/compute_errors.py` — pairs student interactions and uses `lib.chatgeneration.generate_chat_completion()` to ask the LLM whether an answer contains a misconception and to assign a subtopic. Code attempts to use `llama3.2:3b` by default (local Ollama) and falls back to heuristics.
- Bloom classification: `lib/analytics_agent.classify_bloom()` — packages student/assistant exchange into a JSON classifier prompt and uses the configured model (defaults to `DEFAULT_MODELS['coding_companion']`, typically `llama3.2:3b`).
- Count/difficulty computations: `scripts/compute_counts.py` and `scripts/compute_topic_difficulty.py` (heuristic, time-on-task based) — do not require an LLM.

Model mapping summary:
- `llama3.2:3b` (local Ollama) — Bloom classification, misconception labeling, general-purpose local generation used throughout analytics scripts.
- `qwen3:4b` (local Ollama) — topic taxonomy classification (`classify_topics_ollama.py`).
- TF‑IDF / scikit-learn — retrieval fallback and baseline.

## 5. Deployment & reproducibility
- Environment: install dependencies from `requirements.txt`.
- Run the app: `streamlit run chatgpt.py`.
- To reproduce RAG indexes: run `python scripts/build_rag.py` on a machine with `sentence-transformers` & `faiss-cpu`.
- For offline local LLMs: install Ollama and pull required models (`ollama pull llama3.2:3b`, `ollama pull qwen3:4b`). Configure `OLLAMA_URL` in `.env` if needed.

## 6. Evaluation protocol & metrics (recommended for paper)
- Data: logged `ai_generation` events in `logs/activity_log.json` (session-level grouping recommended).
- Tasks & metrics:
  - Misconception detection: precision/recall/F1 compared to human-annotated labels (sample and annotate a validation set).
  - Subtopic classification: micro/macro F1.
  - Retrieval: Recall@k and MRR@k where ground-truth context exists.
  - Dashboard-level validation: instructor ratings of top-N difficult topics judged against `topic_difficulty.json` outputs.
- Baselines: keyword heuristics, TF‑IDF retrieval, local LLM vs. hosted model variants.

## 7. Reproducibility checklist (for paper)
- Archive `data/vector_index/*` artifacts and `data/analytics/*` outputs used in analyses.
- Pin package versions with `pip freeze > requirements.txt` and attach environment YAML if using conda.
- Document Ollama model versions (image digest) or hosted model identifiers and API versions.

## 8. Where to find code implementing each component
- RAG retriever: `lib/rag.py`
- Generation wrapper (multi-provider): `lib/chatgeneration.py`
- Instructor dashboard: `lib/home_views.py`
- Analytics aggregation: `scripts/compute_counts.py`, `scripts/compute_topic_difficulty.py`, `scripts/compute_errors.py`, `scripts/classify_topics_ollama.py`
- Embedding & index files: `data/vector_index/*` (ECE / ROBO)

---

If you want, I can convert this into a single PDF/figure-ready document, produce LaTeX-ready text for inclusion in your research paper, or add example experimental results and plots from your `data/analytics` outputs. Which output format would you like next? 
