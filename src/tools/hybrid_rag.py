"""Local BM25-like retrieval with optional pgvector backend and reciprocal-rank fusion."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    metadata: dict


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def reciprocal_rank_fusion(*ranked_lists: list[Chunk], k: int = 60, limit: int = 5) -> list[Chunk]:
    scores: dict[str, float] = {}
    lookup: dict[str, Chunk] = {}
    for results in ranked_lists:
        for rank, chunk in enumerate(results, 1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (k + rank)
            lookup[chunk.chunk_id] = chunk
    return [lookup[i] for i in sorted(scores, key=scores.get, reverse=True)[:limit]]


class HybridRetriever:
    def __init__(self, chunks: list[Chunk] | None = None, database_url: str | None = None):
        self.chunks = chunks or []
        self.database_url = database_url

    @classmethod
    def from_directory(cls, directory: str | Path, database_url: str | None = None):
        chunks = []
        for path in sorted(Path(directory).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for idx, start in enumerate(range(0, len(text), 1200)):
                part = text[start : start + 1200].strip()
                if part:
                    chunks.append(Chunk(f"{path.stem}#{idx}", part, path.name, {"path": str(path)}))
        return cls(chunks, database_url)

    def search(self, query: str, limit: int = 5) -> list[Chunk]:
        q = set(tokenize(query))
        if not q:
            return []
        ranked = []
        for chunk in self.chunks:
            terms = tokenize(chunk.text)
            freq = {term: terms.count(term) for term in q}
            score = sum(math.log1p(n) for n in freq.values())
            if score:
                ranked.append((score, chunk))
        ranked.sort(key=lambda x: x[0], reverse=True)
        lexical = [c for _, c in ranked[: max(limit * 3, limit)]]
        dense = self._dense_search(query, limit) if self.database_url else []
        return reciprocal_rank_fusion(lexical, dense, limit=limit) if dense else lexical[:limit]

    def _dense_search(self, query: str, limit: int) -> list[Chunk]:
        """Optional integration point; returns no vector results until an embedding backend is configured."""
        return []
