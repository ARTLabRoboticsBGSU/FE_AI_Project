# FE-AI System Architecture

This document describes the high-level architecture of FE-AI (Student UI + Instructor UI), data flows, and component responsibilities.

```mermaid
flowchart TB
  subgraph UI[User Interfaces]
    A[Student UI (Streamlit pages)]
    B[Instructor UI (Analytics Dashboard)]
  end

  subgraph App[Streamlit App Server]
    C[chatgpt.py - App Router]
    D[Pages (pages/*)]
    E[lib/* utilities]
  end

  subgraph Services[Local/External Services]
    F[Local Ollama daemon (optional) \n (OLLAMA_URL)]
    G[Hosted APIs (OpenAI, Anthropic, HF, Cohere, Groq)]
  end

  subgraph Data[Persistence]
    H[logs/activity_log.json] --> I[data/sessions.json]
    J[data/vector_index/* - FAISS indexes + docs.jsonl]
    K[data/analytics/* - computed metrics files]
  end

  A --> C
  B --> C
  C --> D
  D --> E
  E --> J
  E --> H
  E --> K
  E --> F
  E --> G
  F --> E
  G --> E

  style UI fill:#f9f,stroke:#333,stroke-width:1px
  style App fill:#eef,stroke:#333,stroke-width:1px
  style Services fill:#efe,stroke:#333,stroke-width:1px
  style Data fill:#ffe,stroke:#333,stroke-width:1px
```

Key areas:
- Student UI: Streamlit pages for student-facing features (AI Sandbox, Coding Companion, etc.).
- Instructor UI: Instructor Dashboard (`lib/home_views.py`) showing heatmap, misconception charts, Bloom distribution, and At-Risk student lists.
- App Router: `chatgpt.py` initialises UI, applies theme, and routes to pages.
- Utilities: `lib/` contains RAG (`lib/rag.py`), generation wrapper (`lib/chatgeneration.py`), analytics helpers, session management, and the runtime HTTP guard (`lib/disable_http.py`).
- Data stores: analytics outputs and vector indexes are persisted under `data/`.

Data flow summary:
1. Students interact with the Student UI; interactions are logged to `logs/activity_log.json`.
2. Analytics scripts (`scripts/*`) process logs and write `data/analytics/*` and `data/topic_difficulty.json`.
3. RAG uses precomputed vector indexes in `data/vector_index/*` to retrieve contexts; fallback to TF‑IDF is available when embeddings are not present.
4. Local Ollama (if configured) and other providers are used via `lib/chatgeneration.py` for classification/generation tasks.
