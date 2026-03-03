from __future__ import annotations

from src.domain.models import RetrievedChunk
from src.storage.postgres import get_connection


def search_lexical(
    query: str,
    k: int,
    namespace: str = "papers",
    document_filter: str | None = None,
) -> list[RetrievedChunk]:
    doc_filter_clause = ""
    doc_filter_params: tuple[str, ...] = ()
    if document_filter and document_filter.strip():
        # Normalise spaces/underscores to % so that "Peugeot 5008" matches
        # doc_id "peugeot_5008" and vice-versa.
        normalised = "%".join(document_filter.strip().split())
        pattern = f"%{normalised}%"
        doc_filter_clause = " AND (d.title ILIKE %s OR d.doc_id ILIKE %s)"
        doc_filter_params = (pattern, pattern)

    with get_connection(namespace) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""
                    SELECT c.chunk_id, c.doc_id, d.title AS paper_title, c.content, c.content_type,
                           c.page, c.source_ref, c.metadata, paradedb.score(c.chunk_id) AS score
                    FROM chunks c
                    JOIN documents d ON d.doc_id = c.doc_id
                    WHERE c.content @@@ %s{doc_filter_clause}
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, *doc_filter_params, k),
                )
                rows = cur.fetchall()
            except Exception:
                conn.rollback()
                cur.execute(
                    f"""
                    SELECT c.chunk_id, c.doc_id, d.title AS paper_title, c.content, c.content_type,
                           c.page, c.source_ref, c.metadata,
                           ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', %s)) AS score
                    FROM chunks c
                    JOIN documents d ON d.doc_id = c.doc_id
                    WHERE c.content_tsv @@ websearch_to_tsquery('english', %s){doc_filter_clause}
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, query, *doc_filter_params, k),
                )
                rows = cur.fetchall()

    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            paper_title=row.get("paper_title"),
            content=row["content"],
            content_type=row["content_type"],
            page=row["page"],
            source_ref=row["source_ref"],
            metadata=row["metadata"] or {},
            score=float(row["score"] or 0.0),
        )
        for row in rows
    ]
