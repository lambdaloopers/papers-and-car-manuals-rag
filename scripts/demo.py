from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from src.rag.chat import run_chat_session
from src.rag.prompts import PAPERS_SYSTEM_PROMPT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive RAG chat for scientific papers."
    )
    parser.add_argument(
        "--namespace", default="papers", help="Postgres schema namespace."
    )
    parser.add_argument(
        "--input-dir",
        default="./data/arxiv_recent_smoke",
        help="Directory with PDF files to ingest.",
    )
    parser.add_argument(
        "--force-ingest",
        action="store_true",
        help="Re-ingest even if documents already exist.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    run_chat_session(
        namespace=args.namespace,
        input_dir=Path(args.input_dir),
        system_prompt=PAPERS_SYSTEM_PROMPT,
        title="Papers RAG Chat",
        force_ingest=args.force_ingest,
    )


if __name__ == "__main__":
    main()
