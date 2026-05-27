# RAG (Retrieval-Augmented Generation) — Knowledge Base and Indexing

This project implements a lightweight RAG pipeline designed for offline-first operation with an optional local Ollama generation path.

Where the knowledge base lives
- Documents (source corpus): data/vector_index/<COURSE>/docs.jsonl
  - Example paths: `data/vector_index/ECE/docs.jsonl`, `data/vector_index/ROBO/docs.jsonl`.
- Vector indexes: FAISS index files per course: `data/vector_index/<COURSE>/index.faiss`.

Vector database and embeddings
- Vector DB: FAISS (index files are stored as `index.faiss` under each course folder).
- Embeddings: by default produced using `sentence-transformers` (see `lib/rag.py`).
  - The code attempts to import `SentenceTransformer` and use a local embedding model.
  - When sentence-transformers is unavailable or Ollama embeddings are not available, the code falls back to a TF‑IDF retrieval using `scikit-learn` (`TfidfVectorizer` + cosine similarity via `linear_kernel`).

Key files and components
- `lib/rag.py` — RAG retriever implementation
  - Responsibilities: load FAISS index, map query -> embedding via SentenceTransformer, perform similarity search, apply similarity thresholding, and return top-K context (project currently uses top-1 retrieval for coding companion pages).
  - TF‑IDF fallback: if embedding model not available, `lib/rag.py` constructs a TF‑IDF matrix over the corpus and uses cosine similarity.
- `scripts/build_rag.py` — (re)builds indexes from documents and writes `docs.jsonl` + `index.faiss` into `data/vector_index/<COURSE>/`.

Configuration
- Embedding model selection and OLLAMA integration are controlled via environment variables and `config.py` entries. `OLLAMA_URL` points to the local Ollama daemon (default `http://localhost:11434`).

Usage notes
- If you need reproducible indexing, run `scripts/build_rag.py` on a machine with `sentence-transformers`, `faiss-cpu`, and sufficient memory.
- If running on a machine without GPU, prefer `faiss-cpu` to avoid build issues.
