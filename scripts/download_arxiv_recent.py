from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _build_query_url(search_query: str, max_results: int) -> str:
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"


def _safe_filename(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def _parse_entries(xml_payload: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_payload)
    records: list[dict[str, str]] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or "").strip()

        if not entry_id:
            continue

        arxiv_id = entry_id.rsplit("/", maxsplit=1)[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        authors = [
            (author.findtext("atom:name", default="", namespaces=ATOM_NS) or "").strip()
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [cat.attrib.get("term", "").strip() for cat in entry.findall("atom:category", ATOM_NS)]

        records.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "summary": summary,
                "published": published,
                "updated": updated,
                "pdf_url": pdf_url,
                "authors": authors,
                "categories": categories,
            }
        )

    return records


def _download_file(url: str, target_path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "local-multimodal-rag/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        content = response.read()
    target_path.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download recent arXiv papers (PDF + metadata).")
    parser.add_argument("--max-results", type=int, default=30, help="Number of recent papers to download.")
    parser.add_argument(
        "--search-query",
        default="cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
        help="arXiv API search query. Example: cat:cs.AI OR cat:cs.LG",
    )
    parser.add_argument("--output-dir", default="./data/arxiv_recent", help="Destination folder for PDFs.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.4,
        help="Delay between PDF downloads to avoid rate limiting.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.jsonl"

    query_url = _build_query_url(search_query=args.search_query, max_results=args.max_results)
    with urllib.request.urlopen(query_url, timeout=60) as response:
        xml_payload = response.read()

    entries = _parse_entries(xml_payload)
    if not entries:
        print("No entries returned from arXiv API.")
        return

    downloaded = 0
    with metadata_path.open("w", encoding="utf-8") as metadata_file:
        for index, entry in enumerate(entries, start=1):
            file_name = f"{index:02d}_{_safe_filename(entry['arxiv_id'])}.pdf"
            pdf_path = output_dir / file_name

            try:
                _download_file(entry["pdf_url"], pdf_path)
                downloaded += 1
                entry["local_pdf_path"] = str(pdf_path)
                metadata_file.write(json.dumps(entry, ensure_ascii=True) + "\n")
                print(f"[{index:02d}/{len(entries):02d}] Downloaded {file_name}")
            except Exception as exc:
                print(f"[{index:02d}/{len(entries):02d}] Failed {entry['arxiv_id']}: {exc}")

            time.sleep(max(args.sleep_seconds, 0.0))

    print(f"Done. Downloaded {downloaded}/{len(entries)} PDFs to {output_dir}")
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()
