from src.domain.models import RetrievedChunk
from src.retrieval.fusion import rrf_fuse


def _chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id="d1",
        content=f"content-{chunk_id}",
        content_type="text",
        page=1,
        source_ref=None,
        metadata={},
        score=score,
    )


def test_rrf_fuse_merges_rankings() -> None:
    lexical = [_chunk("a", 1.0), _chunk("b", 0.8), _chunk("c", 0.5)]
    vector = [_chunk("b", 0.9), _chunk("d", 0.7), _chunk("a", 0.6)]

    fused = rrf_fuse(lexical, vector, k=3, rrf_k=60)
    fused_ids = [item.chunk_id for item in fused]

    assert fused_ids[0] in {"a", "b"}
    assert len(fused) == 3
    assert set(fused_ids).issubset({"a", "b", "c", "d"})
