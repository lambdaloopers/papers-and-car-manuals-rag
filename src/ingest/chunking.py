from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.domain.models import ChunkRecord
from src.ingest.docling_parser import ParsedElement


def chunk_elements(doc_id: str, elements: list[ParsedElement]) -> list[ChunkRecord]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    chunks: list[ChunkRecord] = []
    for element_idx, element in enumerate(elements):
        if element.content_type == "table":
            chunks.append(
                ChunkRecord(
                    chunk_id=f"{doc_id}:{element_idx}:0",
                    doc_id=doc_id,
                    content=element.content,
                    content_type=element.content_type,  # type: ignore[arg-type]
                    page=element.page,
                    section=element.section,
                    source_ref=element.source_ref,
                    metadata={"element_index": element_idx, "part_index": 0},
                )
            )
        else:
            parts = [p for p in splitter.split_text(element.content) if p.strip()] or [element.content]
            for part_idx, part in enumerate(parts):
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{doc_id}:{element_idx}:{part_idx}",
                        doc_id=doc_id,
                        content=part,
                        content_type=element.content_type,  # type: ignore[arg-type]
                        page=element.page,
                        section=element.section,
                        source_ref=element.source_ref,
                        metadata={"element_index": element_idx, "part_index": part_idx},
                    )
                )
    return chunks
