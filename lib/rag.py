"""
Simple Retrieval-Augmented-Generation (RAG) helper using LangChain + FAISS.

Provides a small, local retriever that can ingest text and PDF files and
build a FAISS index using HuggingFace embeddings. Index is stored under
`data/vector_index` by default.

This module is intentionally lightweight and uses lazy imports so the app
still runs if dependencies are not installed. See `scripts/build_rag.py`
for a simple index builder.
"""
import os
from typing import List
import json
import math

DEFAULT_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vector_index")


class RAGRetriever:
    """RAG retriever with two load modes:
    - Prefer LangChain FAISS when available.
    - Fallback to direct sentence-transformers + faiss implementation.
    """
    def __init__(self, index_dir: str = DEFAULT_INDEX_DIR, hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.index_dir = index_dir
        self.hf_embedding_model = hf_embedding_model
        self._mode = None  # 'langchain' or 'native'
        self._vectorstore = None
        self._faiss_index = None
        self._id_to_text = None
        self._embedding_model = None
        self._embeddings = None  # remote/langchain embeddings wrapper when used

    def _ensure_loaded(self):
        if self._mode is not None:
            return
        # NOTE: Prefer a FAISS index when available, but allow a TF-IDF-only
        # fallback if no faiss/index is present or if embeddings cannot be
        # loaded due to offline restrictions. This lets us build `docs.jsonl`
        # from source files and still perform retrieval.
        idx_path = os.path.join(self.index_dir, "index.faiss")
        docs_path = os.path.join(self.index_dir, "docs.jsonl")
        if not os.path.exists(docs_path):
            raise RuntimeError(f"Docs file not found in {self.index_dir}. Run scripts/build_rag.py to create them.")

        # Load metadata (docs.jsonl)
        id_to_text = []
        with open(docs_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                try:
                    id_to_text.append(json.loads(line)['text'])
                except Exception:
                    continue

        # Try to load a FAISS index if present and faiss is importable
        try:
            import faiss
            if os.path.exists(idx_path):
                try:
                    index = faiss.read_index(idx_path)
                    # Try to use local SentenceTransformer for native embedding
                    try:
                        from sentence_transformers import SentenceTransformer
                        self._embedding_model = SentenceTransformer(self.hf_embedding_model)
                        self._faiss_index = index
                        self._id_to_text = id_to_text
                        self._mode = 'native'
                        return
                    except Exception:
                        # If sentence-transformers cannot be loaded (e.g., offline),
                        # fall through to TF-IDF fallback using the loaded FAISS
                        # index is ignored in that case.
                        pass
                except Exception:
                    # if reading index fails, continue to TF-IDF fallback
                    pass
        except Exception:
            # faiss not available; continue to TF-IDF fallback
            pass

        # TF-IDF offline fallback (works when docs.jsonl exists)
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import linear_kernel

            tfidf = TfidfVectorizer(stop_words='english')
            tfidf_matrix = tfidf.fit_transform(id_to_text)

            self._tfidf_vectorizer = tfidf
            self._tfidf_matrix = tfidf_matrix
            self._id_to_text = id_to_text
            self._mode = 'tfidf'
            return
        except Exception:
            raise RuntimeError(
                "Could not initialize any retrieval backend. Install faiss-cpu and sentence-transformers, or scikit-learn for TF-IDF fallback."
            )

    def retrieve(self, query: str, k: int = 4) -> List[dict]:
        """Return top-k documents as dicts {"text": ... , "score": ...}.
        """
        self._ensure_loaded()
        if self._mode == 'langchain':
            docs = self._vectorstore.similarity_search(query, k=k)
            # Normalize to dicts
            out = []
            for d in docs:
                out.append({"text": getattr(d, 'page_content', str(d)), "score": None})
            return out

        # native or remote_faiss modes
        import numpy as np
        if self._mode == 'native':
            emb = self._embedding_model.encode([query], convert_to_numpy=True)
            emb = emb.astype('float32')
            D, I = self._faiss_index.search(emb, k)
        elif self._mode == 'tfidf':
            # Use TF-IDF offline fallback for similarity (cosine via linear_kernel)
            try:
                from sklearn.metrics.pairwise import linear_kernel
            except Exception:
                raise RuntimeError("TF-IDF fallback requires scikit-learn. Install scikit-learn or provide a local SentenceTransformer model.")
            q_vec = self._tfidf_vectorizer.transform([query])
            sims = linear_kernel(q_vec, self._tfidf_matrix).flatten()
            # Get top-k indices sorted by similarity
            top_idx = sims.argsort()[::-1][:k]
            D = [sims[top_idx].tolist()]
            I = [top_idx.tolist()]
        elif self._mode == 'remote_faiss':
            # compute embedding via remote/langchain embeddings wrapper
            # try embed_documents, fall back to embed_query
            try:
                vec = self._embeddings.embed_documents([query])[0]
            except Exception:
                vec = self._embeddings.embed_query(query)
            emb = np.array([vec], dtype='float32')
            D, I = self._faiss_index.search(emb, k)
        else:
            raise RuntimeError("Unsupported RAG mode for retrieval")

        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0 or idx >= len(self._id_to_text):
                continue
            results.append({"text": self._id_to_text[idx], "score": float(score)})
        return results

    @staticmethod
    def _split_text(text: str, chunk_size: int = 800, overlap: int = 100):
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = max(end - overlap, end)
        return chunks

    @staticmethod
    def build_index(source_dir: str, index_dir: str = DEFAULT_INDEX_DIR, hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Build a FAISS index from .txt and .pdf files using sentence-transformers + faiss.

        Saves `index.faiss` and `docs.jsonl` under `index_dir`.
        """
        try:
            import faiss
            import numpy as np
            from sentence_transformers import SentenceTransformer
            from PyPDF2 import PdfReader
        except Exception as e:
            raise RuntimeError("RAG build dependencies are missing. Install sentence-transformers, faiss-cpu, and PyPDF2") from e

        texts = []
        for root, dirs, files in os.walk(source_dir):
            for fname in files:
                path = os.path.join(root, fname)
                if fname.lower().endswith('.txt'):
                    with open(path, 'r', encoding='utf-8') as fh:
                        texts.append(fh.read())
                elif fname.lower().endswith('.pdf'):
                    try:
                        reader = PdfReader(path)
                        pages = []
                        for p in reader.pages:
                            pages.append(p.extract_text() or "")
                        texts.append('\n'.join(pages))
                    except Exception:
                        continue
                elif fname.lower().endswith('.pptx'):
                    try:
                        from pptx import Presentation
                        prs = Presentation(path)
                        slides_text = []
                        for slide in prs.slides:
                            slide_lines = []
                            for shape in slide.shapes:
                                try:
                                    if hasattr(shape, 'text') and shape.text:
                                        slide_lines.append(shape.text)
                                except Exception:
                                    continue
                            slides_text.append('\n'.join(slide_lines))
                        texts.append('\n\n'.join(slides_text))
                    except Exception:
                        continue

        if not texts:
            raise RuntimeError(f"No documents found in {source_dir} (supported: .txt, .pdf)")

        # Chunk texts
        chunks = []
        for t in texts:
            for c in RAGRetriever._split_text(t, chunk_size=800, overlap=100):
                chunks.append(c)

        model = SentenceTransformer(hf_embedding_model)
        embeddings = model.encode(chunks, convert_to_numpy=True)
        embeddings = embeddings.astype('float32')

        d = embeddings.shape[1]
        index = faiss.IndexFlatL2(d)
        index.add(embeddings)

        os.makedirs(index_dir, exist_ok=True)
        faiss_idx_path = os.path.join(index_dir, 'index.faiss')
        faiss.write_index(index, faiss_idx_path)

        docs_path = os.path.join(index_dir, 'docs.jsonl')
        with open(docs_path, 'w', encoding='utf-8') as fh:
            for c in chunks:
                fh.write(json.dumps({'text': c}, ensure_ascii=False) + "\n")

        return index_dir
