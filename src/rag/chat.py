from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.ingest.loaders import list_pdf_files, load_paper_titles
from src.ingest.pipeline import ingest_pdf_papers
from src.rag.chain import answer_query
from src.storage.postgres import has_documents, init_schema

IngestFn = Callable[[Path, str | None, str], tuple[int, int]]


def _run_ingest(input_dir: Path, namespace: str, ingest_fn: IngestFn) -> None:
    pdf_files = list_pdf_files(input_dir)
    if not pdf_files:
        print(f"  No PDF files found in {input_dir}")
        return
    paper_titles = load_paper_titles(input_dir)
    total = len(pdf_files)
    print(f"  Found {total} PDF file(s).")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"\n[{i}/{total}] {pdf.name}")
        text_count, vision_count = ingest_fn(pdf, paper_titles.get(pdf.stem), namespace)
        print(f"  Done: {text_count} text chunks, {vision_count} vision chunks")


def run_chat_session(
    namespace: str,
    input_dir: Path,
    system_prompt: str,
    title: str,
    force_ingest: bool = False,
    ingest_fn: IngestFn = ingest_pdf_papers,
) -> None:
    print(f"\nInitializing namespace '{namespace}'...")
    init_schema(namespace)

    if force_ingest or not has_documents(namespace):
        print(f"Ingesting documents from {input_dir}...")
        _run_ingest(input_dir, namespace, ingest_fn)
        if not has_documents(namespace):
            print("No documents were ingested. Check that PDF files exist in the input directory.")
            return

    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"  Namespace: {namespace}")
    print(f"  Type 'exit' or press Ctrl+C to quit.")
    print(f"{'=' * 50}\n")

    history: list[dict[str, str]] = []

    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        result = answer_query(
            question,
            namespace=namespace,
            conversation_history=history,
            system_prompt=system_prompt,
        )

        print(f"\nAssistant: {result.answer}")

        if result.citations:
            sources = []
            seen: set[str] = set()
            for c in result.citations:
                label = c.paper_title or c.doc_id
                page_info = f" p.{c.page}" if c.page else ""
                entry = f"{label}{page_info}"
                if entry not in seen:
                    seen.add(entry)
                    sources.append(entry)
            print(f"Sources: {' · '.join(sources)}")

        print()

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result.answer})
