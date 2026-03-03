from __future__ import annotations

from openai import OpenAI
from pgvector.psycopg import register_vector

from src.config import get_settings
from src.domain.models import RetrievedChunk
from src.storage.postgres import get_connection


def _embed_query(query: str) -> list[float]:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=settings.openai_embedding_model, input=[query])
    return response.data[0].embedding


def search_vector(
    query: str,
    k: int,
    namespace: str = "papers",
    document_filter: str | None = None,
) -> list[RetrievedChunk]:
    query_embedding = _embed_query(query)

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
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.chunk_id, c.doc_id, d.title AS paper_title, c.content, c.content_type,
                       c.page, c.source_ref, c.metadata, (1 - (c.embedding <=> %s::vector)) AS score
                FROM chunks c
                JOIN documents d ON d.doc_id = c.doc_id
                WHERE c.embedding IS NOT NULL{doc_filter_clause}
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, *doc_filter_params, query_embedding, k),
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
