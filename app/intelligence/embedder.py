# app/intelligence/embedder.py
import asyncio
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import Optional

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("[Embedder] Loading sentence-transformer model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[Embedder] Model loaded OK")
    return _model


def chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks, current, length = [], [], 0
    for word in words:
        current.append(word)
        length += len(word) + 1
        if length >= max_chars:
            chunks.append(" ".join(current))
            current = current[-20:]
            length = sum(len(w) + 1 for w in current)
    if current:
        chunks.append(" ".join(current))
    return chunks


async def rerank_chunks(query: str, chunks: list[str], top_k: int = 8) -> list[str]:
    """FAISS cosine similarity rerank — return top_k most relevant chunks."""
    if not chunks:
        return []

    model = get_model()

    def _rerank():
        q_vec = model.encode([query], normalize_embeddings=True).astype("float32")
        c_vecs = model.encode(chunks, normalize_embeddings=True).astype("float32")
        index = faiss.IndexFlatIP(c_vecs.shape[1])
        index.add(c_vecs)
        distances, indices = index.search(q_vec, min(top_k, len(chunks)))
        return [chunks[i] for i in indices[0]]

    return await asyncio.to_thread(_rerank)


async def embed_documents(query: str, documents: list[dict], top_k: int = 8) -> list[str]:
    """Chunk all documents and return top_k most relevant chunks."""
    all_chunks = []
    for doc in documents:
        content = doc.get("content", "")
        if content and len(content) > 50:
            chunks = chunk_text(content)
            all_chunks.extend(chunks)

    if not all_chunks:
        return []

    print(f"[Embedder] {len(all_chunks)} chunks → reranking to top {top_k}")
    top_chunks = await rerank_chunks(query, all_chunks, top_k=top_k)
    return top_chunks