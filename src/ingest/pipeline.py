from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.domain.models import ChunkRecord, DocumentRecord
from src.ingest.chunking import chunk_elements
from src.ingest.chunking_cars import chunk_elements_cars
from src.ingest.docling_parser import ParsedElement, parse_pdf
from src.ingest.image_export import export_element_image, is_image_like
from src.ingest.vision_enrichment import build_vision_chunk
from src.storage.repositories import ChunkRepository, DocumentRepository

_VISION_WORKERS = 8


def _cleanup_assets_for_doc(assets_dir: Path, doc_id: str) -> None:
    """Remove exported image files for this doc from assets_dir (already embedded and saved)."""
    if not assets_dir.is_dir():
        return
    for path in assets_dir.glob(f"{doc_id}_*.png"):
        try:
            path.unlink()
        except OSError:
            pass


def _enrich_one(
    *,
    element_idx: int,
    element: ParsedElement,
    document: Any,
    doc_id: str,
    resolved_title: str,
    assets_dir: Path,
) -> ChunkRecord | None:
    image_path = export_element_image(
        element=element.raw,
        document=document,
        assets_dir=assets_dir,
        doc_id=doc_id,
        element_index=element_idx,
    )
    if image_path is None:
        return None
    chunk = build_vision_chunk(
        chunk_id=f"{doc_id}:vision:{element_idx}",
        doc_id=doc_id,
        image_path=image_path,
        page=element.page,
        source_ref=element.source_ref,
        content_type=element.content_type,
    )
    chunk.metadata["paper_title"] = resolved_title
    return chunk


def _ingest_with_chunks(
    *,
    title: str | None,
    namespace: str,
    doc_record: DocumentRecord,
    base_chunks: list[ChunkRecord],
    elements: list[ParsedElement],
    document: Any,
) -> tuple[int, int]:
    settings = get_settings()

    document_repo = DocumentRepository(namespace=namespace)
    chunk_repo = ChunkRepository(namespace=namespace)
    resolved_title = (title or "").strip() or doc_record.doc_id
    n_visual = sum(1 for e in elements if is_image_like(e.content_type))
    print(f"  [1/4] Parsed {len(elements)} elements ({n_visual} figures/tables)")

    doc_record.title = resolved_title
    document_repo.upsert_document(doc_record)

    # Step 2: Chunk text
    print(f"  [2/4] Chunking text...", flush=True)
    for chunk in base_chunks:
        chunk.metadata["paper_title"] = resolved_title
    print(f"  [2/4] {len(base_chunks)} text chunks")

    # Step 3: Vision enrichment (parallel, skipping already-ingested elements)
    existing_ids = chunk_repo.fetch_existing_chunk_ids(doc_record.doc_id)
    vision_candidates = [
        (idx, elem)
        for idx, elem in enumerate(elements)
        if is_image_like(elem.content_type)
        and f"{doc_record.doc_id}:vision:{idx}" not in existing_ids
    ]
    skipped = n_visual - len(vision_candidates)
    skip_note = f", {skipped} already ingested" if skipped else ""
    print(f"  [3/4] Vision enrichment: {len(vision_candidates)} elements{skip_note} ({_VISION_WORKERS} workers)...", flush=True)

    vision_chunks: list[ChunkRecord] = []
    if vision_candidates:
        completed = 0
        with ThreadPoolExecutor(max_workers=min(_VISION_WORKERS, len(vision_candidates))) as executor:
            futures = {
                executor.submit(
                    _enrich_one,
                    element_idx=idx,
                    element=elem,
                    document=document,
                    doc_id=doc_record.doc_id,
                    resolved_title=resolved_title,
                    assets_dir=settings.assets_dir,
                ): idx
                for idx, elem in vision_candidates
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        vision_chunks.append(result)
                except Exception as exc:
                    element_idx = futures[future]
                    print(f"\n  Warning: vision enrichment failed for element {element_idx}: {exc}")
                completed += 1
                print(f"        {completed}/{len(vision_candidates)} done", end="\r", flush=True)
        print(f"  [3/4] Vision enrichment complete: {len(vision_chunks)} chunks          ")

    # Step 4: Embed and save
    print(f"  [4/4] Embedding and saving to database...", flush=True)
    chunk_repo.upsert_chunks(base_chunks + vision_chunks, with_embeddings=True)
    print(f"  [4/4] Saved.")

    # Cleanup: remove exported images for this doc (no longer needed after embedding)
    _cleanup_assets_for_doc(settings.assets_dir, doc_record.doc_id)

    return len(base_chunks), len(vision_chunks)


def ingest_pdf_papers(pdf_path: Path, paper_title: str | None = None, namespace: str = "papers") -> tuple[int, int]:
    print("  [1/4] Parsing with Docling...", flush=True)
    doc_record, elements, document = parse_pdf(pdf_path)
    base_chunks = chunk_elements(doc_record.doc_id, elements)
    return _ingest_with_chunks(
        title=paper_title,
        namespace=namespace,
        doc_record=doc_record,
        base_chunks=base_chunks,
        elements=elements,
        document=document,
    )


def ingest_pdf_cars(pdf_path: Path, manual_title: str | None = None, namespace: str = "cars") -> tuple[int, int]:
    print("  [1/4] Parsing with Docling...", flush=True)
    doc_record, elements, document = parse_pdf(pdf_path)
    base_chunks = chunk_elements_cars(doc_record.doc_id, elements)
    return _ingest_with_chunks(
        title=manual_title,
        namespace=namespace,
        doc_record=doc_record,
        base_chunks=base_chunks,
        elements=elements,
        document=document,
    )


def ingest_pdf(pdf_path: Path, paper_title: str | None = None, namespace: str = "papers") -> tuple[int, int]:
    """Backward-compatible alias for papers ingestion."""
    return ingest_pdf_papers(pdf_path, paper_title=paper_title, namespace=namespace)
