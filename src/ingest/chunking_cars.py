from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.domain.models import ChunkRecord
from src.ingest.docling_parser import ParsedElement

_CARS_CHUNK_SIZE = 2400
_CARS_CHUNK_OVERLAP = 300
_MIN_CHUNK_SIZE = 200


def _merge_small_parts(parts: list[str]) -> list[str]:
    cleaned = [part.strip() for part in parts if part.strip()]
    if not cleaned:
        return []

    merged: list[str] = [cleaned[0]]
    for part in cleaned[1:]:
        if len(merged[-1]) < _MIN_CHUNK_SIZE:
            merged[-1] = f"{merged[-1]}\n\n{part}"
        else:
            merged.append(part)

    if len(merged) > 1 and len(merged[-1]) < _MIN_CHUNK_SIZE:
        merged[-2] = f"{merged[-2]}\n\n{merged[-1]}"
        merged.pop()

    return merged


def _build_group_chunks(
    doc_id: str,
    group_index: int,
    group_elements: list[tuple[int, ParsedElement]],
    splitter: RecursiveCharacterTextSplitter,
) -> list[ChunkRecord]:
    if not group_elements:
        return []

    first_element = group_elements[0][1]
    page_label = str(first_element.page) if first_element.page is not None else "na"
    combined_text = "\n\n".join(element.content for _, element in group_elements if element.content.strip())
    if not combined_text.strip():
        return []

    raw_parts = splitter.split_text(combined_text)
    parts = _merge_small_parts(raw_parts) or [combined_text.strip()]
    element_indices = [idx for idx, _ in group_elements]

    chunks: list[ChunkRecord] = []
    for part_index, part in enumerate(parts):
        chunks.append(
            ChunkRecord(
                chunk_id=f"{doc_id}:p{page_label}:g{group_index}:{part_index}",
                doc_id=doc_id,
                content=part,
                content_type="text",  # type: ignore[arg-type]
                page=first_element.page,
                section=first_element.section,
                source_ref=first_element.source_ref,
                metadata={
                    "group_index": group_index,
                    "part_index": part_index,
                    "element_indices": element_indices,
                },
            )
        )

    return chunks


def chunk_elements_cars(doc_id: str, elements: list[ParsedElement]) -> list[ChunkRecord]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CARS_CHUNK_SIZE,
        chunk_overlap=_CARS_CHUNK_OVERLAP,
    )

    chunks: list[ChunkRecord] = []
    text_group: list[tuple[int, ParsedElement]] = []
    group_index = 0

    def flush_text_group() -> None:
        nonlocal group_index
        chunks.extend(_build_group_chunks(doc_id, group_index, text_group, splitter))
        text_group.clear()
        group_index += 1

    for element_index, element in enumerate(elements):
        if element.content_type == "table":
            if text_group:
                flush_text_group()
            chunks.append(
                ChunkRecord(
                    chunk_id=f"{doc_id}:table:{element_index}:0",
                    doc_id=doc_id,
                    content=element.content,
                    content_type=element.content_type,  # type: ignore[arg-type]
                    page=element.page,
                    section=element.section,
                    source_ref=element.source_ref,
                    metadata={"element_index": element_index, "part_index": 0},
                )
            )
            continue

        if text_group and text_group[-1][1].page != element.page:
            flush_text_group()
        text_group.append((element_index, element))

    if text_group:
        flush_text_group()

    return chunks
