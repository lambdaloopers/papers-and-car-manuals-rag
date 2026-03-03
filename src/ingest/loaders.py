from __future__ import annotations

import json
from pathlib import Path


def list_pdf_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.glob("*.pdf"))


def load_paper_titles(input_dir: Path) -> dict[str, str]:
    """
    Load paper titles from downloader metadata, keyed by PDF stem.
    """
    metadata_path = input_dir / "metadata.jsonl"
    if not metadata_path.exists():
        return {}

    titles_by_stem: dict[str, str] = {}
    with metadata_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            local_pdf_path = entry.get("local_pdf_path")
            title = entry.get("title")
            if not isinstance(local_pdf_path, str) or not isinstance(title, str):
                continue

            stem = Path(local_pdf_path).stem
            if stem and title.strip():
                titles_by_stem[stem] = title.strip()

    return titles_by_stem
