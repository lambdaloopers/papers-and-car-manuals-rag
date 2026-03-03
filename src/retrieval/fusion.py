from __future__ import annotations

from collections import defaultdict

from src.domain.models import RetrievedChunk


def rrf_fuse(
    lexical_results: list[RetrievedChunk],
    vector_results: list[RetrievedChunk],
    k: int,
    rrf_k: int,
    lexical_weight: float = 1.0,
    vector_weight: float = 1.0,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = defaultdict(float)
    payload: dict[str, RetrievedChunk] = {}

    for rank, item in enumerate(lexical_results, start=1):
        scores[item.chunk_id] += lexical_weight * (1.0 / (rrf_k + rank))
        payload[item.chunk_id] = item

    for rank, item in enumerate(vector_results, start=1):
        scores[item.chunk_id] += vector_weight * (1.0 / (rrf_k + rank))
        if item.chunk_id not in payload:
            payload[item.chunk_id] = item

    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:k]
    fused: list[RetrievedChunk] = []
    for chunk_id, score in ranked:
        item = payload[chunk_id]
        fused.append(item.model_copy(update={"score": float(score)}))
    return fused
