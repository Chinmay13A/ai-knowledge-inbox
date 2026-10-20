"""Semantic retrieval: finds the chunks most similar in meaning to a question.

Exact brute-force search: every stored vector (from the current embedding model) is
compared with the query vector in one NumPy matrix product. Vectors are unit length,
so the dot product is the cosine similarity.
"""

import logging
import sqlite3
import time

import numpy as np

from app.ai.embeddings.base import Embedder
from app.models.chunk import RetrievedChunk
from app.repositories import chunks_repo
from app.services.vectors import from_blob

logger = logging.getLogger(__name__)


async def retrieve(
    conn: sqlite3.Connection,
    embedder: Embedder,
    query: str,
    *,
    top_k: int,
    min_score: float,
) -> list[RetrievedChunk]:
    start = time.perf_counter()
    embedder.check_ready()  # e.g. no API key: a clear 503 instead of silently finding nothing
    rows = chunks_repo.embedded_chunks(conn, embedder.model_id)
    if not rows:
        # Nothing searchable yet: don't spend a provider call on the query.
        _log_completed(start, embedder, query, candidates=0, results=[])
        return []

    query_vector = await embedder.embed_query(query)

    vectors = [from_blob(row["embedding"]) for row in rows]
    usable = [i for i, vector in enumerate(vectors) if vector.shape == query_vector.shape]
    if len(usable) < len(rows):
        logger.warning(
            "retrieval.dimension_mismatch",
            extra={"skipped": len(rows) - len(usable), "expected_dims": int(query_vector.shape[0])},
        )
    if not usable:
        _log_completed(start, embedder, query, candidates=0, results=[])
        return []

    rows = [rows[i] for i in usable]
    scores = np.vstack([vectors[i] for i in usable]) @ query_vector

    # Highest score first; ties broken by chunk id so results are deterministic.
    ranked = sorted(
        (i for i in range(len(rows)) if scores[i] >= min_score),
        key=lambda i: (-float(scores[i]), rows[i]["chunk_id"]),
    )[:top_k]
    results = [_to_retrieved(rows[i], float(scores[i])) for i in ranked]
    _log_completed(start, embedder, query, candidates=len(rows), results=results)
    return results


def _to_retrieved(row: sqlite3.Row, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row["chunk_id"],
        item_id=row["item_id"],
        chunk_index=row["chunk_index"],
        text=row["text"],
        score=score,
        item_title=row["item_title"],
        item_url=row["item_url"],
        source_type=row["source_type"],
    )


def _log_completed(
    start: float, embedder: Embedder, query: str, *, candidates: int, results: list[RetrievedChunk]
) -> None:
    logger.info(
        "retrieval.completed",
        extra={
            "query_chars": len(query),  # never the text itself
            "candidates": candidates,
            "returned": len(results),
            "top_score": round(results[0].score, 4) if results else None,
            "model_id": embedder.model_id,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )
