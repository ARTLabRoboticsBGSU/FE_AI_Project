"""Build a simple FAISS index from files under `data/`.

Usage:
    python scripts/build_rag.py --source data/docs --index-dir data/vector_index

This script is intentionally minimal; it uses the `RAGRetriever.build_index`
helper and requires `sentence-transformers` and `faiss-cpu` to be installed.
"""
import argparse
import sys
from lib.rag import RAGRetriever


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data", help="Source directory containing .txt or .pdf files")
    parser.add_argument("--index-dir", default=None, help="Directory to save the index (defaults to data/vector_index)")
    args = parser.parse_args()

    try:
        if args.index_dir:
            index_dir = RAGRetriever.build_index(args.source, index_dir=args.index_dir)
        else:
            index_dir = RAGRetriever.build_index(args.source)
        print(f"Built index at: {index_dir}")
    except Exception as e:
        # If building a FAISS index failed (for example due to offline
        # environment preventing HF model download), fall back to creating
        # a `docs.jsonl` file with chunked text so the app can use TF-IDF
        # retrieval (handled by `lib.rag` TF-IDF fallback).
        print("FAISS build failed, attempting TF-IDF-only docs.jsonl fallback. Error:", e)
        try:
            import os, json
            from pathlib import Path
            from PyPDF2 import PdfReader
            try:
                from pptx import Presentation
                HAVE_PPTX = True
            except Exception:
                HAVE_PPTX = False

            def split_text(text, chunk_size=800, overlap=100):
                if len(text) <= chunk_size:
                    return [text]
                chunks = []
                start = 0
                while start < len(text):
                    end = start + chunk_size
                    chunks.append(text[start:end])
                    start = max(end - overlap, end)
                return chunks

            texts = []
            for root, dirs, files in os.walk(args.source):
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
                    elif HAVE_PPTX and fname.lower().endswith('.pptx'):
                        try:
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
                print('No documents found to build docs.jsonl fallback. Exiting.')
                sys.exit(3)

            chunks = []
            for t in texts:
                for c in split_text(t, chunk_size=800, overlap=100):
                    chunks.append(c)

            index_dir = args.index_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vector_index')
            os.makedirs(index_dir, exist_ok=True)
            docs_path = os.path.join(index_dir, 'docs.jsonl')
            with open(docs_path, 'w', encoding='utf-8') as fh:
                for c in chunks:
                    fh.write(json.dumps({'text': c}, ensure_ascii=False) + "\n")
            print(f'Wrote TF-IDF-only docs.jsonl at: {docs_path}')
            print('TF-IDF fallback ready. RAGRetriever will use TF-IDF for retrieval when FAISS is unavailable.')
            sys.exit(0)
        except Exception as e2:
            print('Fallback failed:', e2)
            sys.exit(2)


if __name__ == '__main__':
    main()
