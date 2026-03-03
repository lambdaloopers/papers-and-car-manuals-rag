from __future__ import annotations

import argparse
from pathlib import Path

from src.ingest.loaders import list_pdf_files, load_paper_titles
from src.ingest.pipeline import ingest_pdf_cars
from src.storage.postgres import init_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest car manual PDFs into local hybrid index.")
    parser.add_argument("--input-dir", default="./data/car_manuals", help="Directory with car manual PDF files.")
    parser.add_argument(
        "--namespace",
        default="cars",
        help="Postgres schema namespace to store car manuals in.",
    )
    args = parser.parse_args()

    init_schema(args.namespace)
    input_dir = Path(args.input_dir)
    pdf_files = list_pdf_files(input_dir)
    manual_titles = load_paper_titles(input_dir)
    print(f"Namespace: {args.namespace}")
    for pdf in pdf_files:
        text_count, vision_count = ingest_pdf_cars(
            pdf,
            manual_title=manual_titles.get(pdf.stem),
            namespace=args.namespace,
        )
        print(f"Ingested {pdf.name}: text_chunks={text_count}, vision_chunks={vision_count}")


if __name__ == "__main__":
    main()
