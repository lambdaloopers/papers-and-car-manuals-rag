from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from src.ingest.pipeline import ingest_pdf_cars
from src.rag.chat import run_chat_session
from src.rag.prompts import CARS_SYSTEM_PROMPT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive RAG chat for vehicle owner manuals.")
    parser.add_argument("--namespace", default="cars", help="Postgres schema namespace.")
    parser.add_argument("--input-dir", default="./data/car_manuals", help="Directory with PDF files to ingest.")
    parser.add_argument("--force-ingest", action="store_true", help="Re-ingest even if documents already exist.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    run_chat_session(
        namespace=args.namespace,
        input_dir=Path(args.input_dir),
        system_prompt=CARS_SYSTEM_PROMPT,
        title="Car Manuals RAG Chat",
        force_ingest=args.force_ingest,
        ingest_fn=ingest_pdf_cars,
    )


if __name__ == "__main__":
    main()
