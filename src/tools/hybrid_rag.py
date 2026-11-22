"""BM25 lexical retrieval plus optional Gemini embeddings and pgvector RRF."""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    metadata: dict = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def split_document(text: str, chunk_chars: int = 1200, overlap_chars: int = 160) -> list[str]:
    if chunk_chars <= 0 or overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("Require chunk_chars > overlap_chars >= 0")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > chunk_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:chunk_chars])
            paragraph = paragraph[chunk_chars - overlap_chars :]
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            overlap = current[-overlap_chars:] if overlap_chars and current else ""
            current = f"{overlap}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


def reciprocal_rank_fusion(*ranked_lists: list[Chunk], k: int = 60, limit: int = 5) -> list[Chunk]:
    scores: dict[str, float] = {}
    lookup: dict[str, Chunk] = {}
    for results in ranked_lists:
        for rank, chunk in enumerate(results, 1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (k + rank)
            lookup[chunk.chunk_id] = chunk
    return [lookup[i] for i in sorted(scores, key=scores.get, reverse=True)[:limit]]


def bm25_search(chunks: list[Chunk], query: str, limit: int = 5, k1: float = 1.5, b: float = 0.75) -> list[Chunk]:
    """Okapi BM25 with inverse document frequency and document-length normalization."""
    terms = set(tokenize(query))
    if not terms or not chunks or limit <= 0:
        return []
    tokenized = [tokenize(chunk.text) for chunk in chunks]
    lengths = [len(doc) for doc in tokenized]
    avg_len = sum(lengths) / max(1, len(lengths))
    doc_freq = {term: sum(term in set(doc) for doc in tokenized) for term in terms}
    scored = []
    n_docs = len(chunks)
    for index, doc in enumerate(tokenized):
        tf: dict[str, int] = {}
        for term in doc:
            if term in terms:
                tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term, count in tf.items():
            df = doc_freq[term]
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            denominator = count + k1 * (1 - b + b * lengths[index] / max(avg_len, 1))
            score += idf * count * (k1 + 1) / denominator
        if score:
            scored.append((score, index))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunks[index] for _, index in scored[:limit]]


class GeminiEmbedder:
    """Gemini embedding adapter. Use ADC on GCP or GEMINI_API_KEY locally."""

    def __init__(self, model: str | None = None, dimensions: int | None = None):
        self.model = model or os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.dimensions = dimensions or int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
        self._client = None

    def embed(self, text: str, task_type: str) -> list[float]:
        try:
            from google import genai
            from google.genai.types import EmbedContentConfig
        except ImportError as exc:
            raise RuntimeError("Install sentinelops[cloud] to create embeddings") from exc
        if self._client is None:
            self._client = genai.Client()
        response = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config=EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions),
        )
        return list(response.embeddings[0].values)


class PgVectorStore:
    """Persistent chunks and cosine-similarity search using PostgreSQL + pgvector."""

    def __init__(self, database_url: str, embedder: GeminiEmbedder | None = None):
        self.database_url = database_url
        self.embedder = embedder or GeminiEmbedder()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install sentinelops[cloud] to use PostgreSQL/pgvector") from exc
        return psycopg.connect(self.database_url)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute("""CREATE TABLE IF NOT EXISTS runbook_chunks (
                chunk_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                embedding vector NOT NULL,
                indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS runbook_chunks_embedding_hnsw_idx ON runbook_chunks USING hnsw (embedding vector_cosine_ops)")

    def upsert(self, chunks: list[Chunk]) -> int:
        self.initialize()
        inserted = 0
        with self._connect() as connection:
            for chunk in chunks:
                vector = self.embedder.embed(chunk.text, "RETRIEVAL_DOCUMENT")
                vector_literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
                connection.execute("""INSERT INTO runbook_chunks(chunk_id, source, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s::jsonb, %s::vector)
                    ON CONFLICT (chunk_id) DO UPDATE SET source=excluded.source, content=excluded.content,
                    metadata=excluded.metadata, embedding=excluded.embedding, indexed_at=now()""",
                    (chunk.chunk_id, chunk.source, chunk.text, json.dumps(chunk.metadata), vector_literal))
                inserted += 1
        return inserted

    def search(self, query: str, limit: int = 5) -> list[Chunk]:
        vector = self.embedder.embed(query, "RETRIEVAL_QUERY")
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
        with self._connect() as connection:
            rows = connection.execute("""SELECT chunk_id, source, content, metadata
                FROM runbook_chunks ORDER BY embedding <=> %s::vector LIMIT %s""",
                (vector_literal, limit)).fetchall()
        return [Chunk(row[0], row[2], row[1], row[3] or {}) for row in rows]


class HybridRetriever:
    def __init__(self, chunks: list[Chunk] | None = None, database_url: str | None = None):
        self.chunks = chunks or []
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.vector_store = PgVectorStore(self.database_url) if self.database_url else None
        self.last_dense_used = False

    @classmethod
    def from_directory(cls, directory: str | Path, database_url: str | None = None):
        chunks: list[Chunk] = []
        for path in sorted(Path(directory).glob("**/*.md")):
            text = path.read_text(encoding="utf-8")
            for idx, part in enumerate(split_document(text)):
                chunks.append(Chunk(f"{path.stem}#{idx}", part, path.name, {"path": str(path)}))
        return cls(chunks, database_url)

    def index(self) -> int:
        if not self.vector_store:
            raise RuntimeError("DATABASE_URL is required to index embeddings")
        return self.vector_store.upsert(self.chunks)

    def search(self, query: str, limit: int = 5) -> list[Chunk]:
        self.last_dense_used = False
        lexical = bm25_search(self.chunks, query, limit=max(limit * 3, limit))
        if not self.vector_store:
            return lexical[:limit]
        try:
            dense = self.vector_store.search(query, limit=max(limit * 3, limit))
        except Exception:
            # Lexical retrieval stays available if credentials or the vector database are down.
            return lexical[:limit]
        self.last_dense_used = bool(dense)
        return reciprocal_rank_fusion(lexical, dense, limit=limit)
