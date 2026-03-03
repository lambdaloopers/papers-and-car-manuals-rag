from __future__ import annotations

from pathlib import Path
from typing import Any


def is_image_like(content_type: str) -> bool:
    return content_type in {"figure", "table"}


def export_element_image(
    *,
    element: Any,
    document: Any,
    assets_dir: Path,
    doc_id: str,
    element_index: int,
) -> Path | None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    get_image = getattr(element, "get_image", None)
    if not callable(get_image):
        return None

    image = get_image(document)
    if image is None:
        return None

    file_path = assets_dir / f"{doc_id}_{element_index:05d}.png"
    image.save(file_path, format="PNG")
    return file_path
