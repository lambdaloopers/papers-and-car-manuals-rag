from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.models import DocumentRecord


@dataclass(frozen=True)
class ParsedElement:
    content: str
    content_type: str
    page: int | None
    section: str | None
    source_ref: str | None
    raw: Any


_converter: Any = None


def _get_converter() -> Any:
    global _converter
    if _converter is None:
        print("  Loading Docling models (first PDF only)...", flush=True)
        _converter = _build_converter()
        print("  Docling models ready.")
    return _converter


def _build_converter() -> Any:
    # Import lazily to avoid hard failures when the environment is not ready yet.
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True

    return DocumentConverter(
        format_options={  # type: ignore[arg-type]
            "pdf": PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def _extract_text_like(item: Any) -> str:
    for attr in ("text", "content", "label", "caption_text"):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(item).strip()


def _infer_content_type(item: Any) -> str:
    class_name = item.__class__.__name__.lower()
    if "code" in class_name:
        return "code"
    if "table" in class_name:
        return "table"
    if "picture" in class_name or "figure" in class_name or "image" in class_name:
        return "figure"
    return "text"


def _extract_page(item: Any) -> int | None:
    def _normalize_page(candidate: Any) -> int | None:
        if isinstance(candidate, int) and candidate > 0:
            return candidate
        return None

    # Direct fields on the element.
    for attr in ("page_no", "page"):
        page = _normalize_page(getattr(item, attr, None))
        if page is not None:
            return page

    # Provenance-based page extraction (Docling commonly stores page in item.prov[*].page_no).
    prov = getattr(item, "prov", None)
    if isinstance(prov, (list, tuple)):
        pages: list[int] = []
        for prov_item in prov:
            page = _normalize_page(getattr(prov_item, "page_no", None))
            if page is None:
                page = _normalize_page(getattr(prov_item, "page", None))
            if page is None and isinstance(prov_item, dict):
                page = _normalize_page(
                    prov_item.get("page_no") or prov_item.get("page")
                )
            if page is not None:
                pages.append(page)
        if pages:
            # For multi-page spans use the first page for stable citation behavior.
            return min(pages)

    # Some objects may expose page on a single nested provenance object.
    if prov is not None:
        page = _normalize_page(getattr(prov, "page_no", None))
        if page is not None:
            return page
        page = _normalize_page(getattr(prov, "page", None))
        if page is not None:
            return page

    return None


def parse_pdf(
    pdf_path: Path, doc_id: str | None = None
) -> tuple[DocumentRecord, list[ParsedElement], Any]:
    converter = _get_converter()
    result = converter.convert(str(pdf_path))
    document = result.document

    resolved_doc_id = doc_id or pdf_path.stem
    doc_record = DocumentRecord(doc_id=resolved_doc_id, source_path=str(pdf_path))

    parsed_elements: list[ParsedElement] = []
    for item, _level in document.iterate_items():
        content_type = _infer_content_type(item)
        if content_type == "table":
            export_fn = getattr(item, "export_to_markdown", None)
            content = export_fn(doc=document).strip() if callable(export_fn) else ""
            if not content:
                content = _extract_text_like(item)
        else:
            content = _extract_text_like(item)
        if not content:
            continue
        parsed_elements.append(
            ParsedElement(
                content=content,
                content_type=content_type,
                page=_extract_page(item),
                section=getattr(item, "label", None),
                source_ref=getattr(item, "self_ref", None),
                raw=item,
            )
        )

    return doc_record, parsed_elements, document
