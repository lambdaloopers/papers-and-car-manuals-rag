from __future__ import annotations

from typing import Iterable

from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.types.json import Json

from src.config import get_settings
from src.domain.models import ChunkRecord, DocumentRecord, RetrievedChunk
from src.storage.postgres import get_connection

NON_EMBEDDABLE_CONTENT_TYPES = {"figure"}


def _embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=settings.openai_embedding_model, input=batch)
        all_embeddings.extend([item.embedding for item in response.data])
    
    return all_embeddings


class DocumentRepository:
    def __init__(self, namespace: str = "papers") -> None:
        self._namespace = namespace

    def upsert_document(self, document: DocumentRecord) -> None:
        with get_connection(self._namespace) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (doc_id, source_path, title, authors, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id)
                    DO UPDATE SET
                        source_path = EXCLUDED.source_path,
                        title = EXCLUDED.title,
                        authors = EXCLUDED.authors,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        document.doc_id,
                        document.source_path,
                        document.title,
                        Json(document.authors),
                        Json(document.metadata),
                    ),
                )
            conn.commit()


class ChunkRepository:
    def __init__(self, namespace: str = "papers") -> None:
        self._namespace = namespace

    def fetch_existing_chunk_ids(self, doc_id: str) -> set[str]:
        with get_connection(self._namespace) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chunk_id FROM chunks WHERE doc_id = %s", (doc_id,))
                return {row["chunk_id"] for row in cur.fetchall()}

    def upsert_chunks(self, chunks: Iterable[ChunkRecord], with_embeddings: bool = True) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return

        embeddings_by_index: dict[int, list[float]] = {}
        if with_embeddings:
            embeddable: list[tuple[int, ChunkRecord]] = [
                (idx, chunk)
                for idx, chunk in enumerate(chunk_list)
                if chunk.content_type not in NON_EMBEDDABLE_CONTENT_TYPES
                and chunk.content.strip()
            ]
            if embeddable:
                embedded_vectors = _embed_texts([chunk.content for _, chunk in embeddable])
                for (chunk_index, _chunk), vector in zip(embeddable, embedded_vectors, strict=False):
                    embeddings_by_index[chunk_index] = vector

        _SQL = """
            INSERT INTO chunks (
                chunk_id, doc_id, content, content_type, page, section,
                source_ref, image_path, metadata, embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
                content = EXCLUDED.content,
                content_type = EXCLUDED.content_type,
                page = EXCLUDED.page,
                section = EXCLUDED.section,
                source_ref = EXCLUDED.source_ref,
                image_path = EXCLUDED.image_path,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
        """
        params = [
            (
                chunk.chunk_id,
                chunk.doc_id,
                chunk.content,
                chunk.content_type,
                chunk.page,
                chunk.section,
                chunk.source_ref,
                chunk.image_path,
                Json(chunk.metadata),
                embeddings_by_index.get(idx),
            )
            for idx, chunk in enumerate(chunk_list)
        ]

        with get_connection(self._namespace) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.executemany(_SQL, params)
            conn.commit()

    def fetch_chunks_by_ids(self, chunk_ids: list[str]) -> list[RetrievedChunk]:
        if not chunk_ids:
            return []

        with get_connection(self._namespace) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, doc_id, content, content_type, page, source_ref, metadata
                    FROM chunks
                    WHERE chunk_id = ANY(%s)
                    """,
                    (chunk_ids,),
                )
                rows = cur.fetchall()

        by_id = {row["chunk_id"]: row for row in rows}
        ordered = []
        for chunk_id in chunk_ids:
            row = by_id.get(chunk_id)
            if row is None:
                continue
            ordered.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    doc_id=row["doc_id"],
                    content=row["content"],
                    content_type=row["content_type"],
                    page=row["page"],
                    source_ref=row["source_ref"],
                    metadata=row["metadata"] or {},
                    score=0.0,
                )
            )
        return ordered
