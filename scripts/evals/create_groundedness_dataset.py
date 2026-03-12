from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update LangSmith dataset for groundedness eval.")
    parser.add_argument(
        "--dataset-name",
        default="groundedness-v1",
        help="LangSmith dataset name.",
    )
    parser.add_argument(
        "--examples-path",
        default="./data/evals/groundedness_examples.jsonl",
        help="Path to JSONL file with eval examples.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append examples even if the dataset already has examples.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing dataset with the same name before uploading examples.",
    )
    return parser.parse_args()


def load_examples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Examples file not found: {path}")

    examples: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        inputs = row.get("inputs")
        if not isinstance(inputs, dict) or "question" not in inputs or "namespace" not in inputs:
            raise ValueError(f"Invalid example at line {line_no}: expected inputs.question and inputs.namespace")
        outputs = row.get("outputs") or {}
        if not isinstance(outputs, dict):
            raise ValueError(f"Invalid example at line {line_no}: outputs must be an object when provided")

        gold_chunk_ids = outputs.get("gold_chunk_ids")
        if gold_chunk_ids is not None:
            if not isinstance(gold_chunk_ids, list) or not all(isinstance(item, str) for item in gold_chunk_ids):
                raise ValueError(
                    f"Invalid example at line {line_no}: outputs.gold_chunk_ids must be a list of strings"
                )

        gold_source_refs = outputs.get("gold_source_refs")
        if gold_source_refs is not None:
            if not isinstance(gold_source_refs, list) or not all(isinstance(item, str) for item in gold_source_refs):
                raise ValueError(
                    f"Invalid example at line {line_no}: outputs.gold_source_refs must be a list of strings"
                )

        examples.append(
            {
                "inputs": inputs,
                # v1 groundedness is judged against retrieved evidence, so reference outputs are optional.
                "outputs": outputs,
                "metadata": row.get("metadata") or {},
            }
        )
    return examples


def get_or_create_dataset(client: Client, dataset_name: str):
    existing = list(client.list_datasets(dataset_name=dataset_name, limit=1))
    if existing:
        return existing[0], False
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Groundedness eval inputs for cars and papers namespaces.",
    )
    return dataset, True


def main() -> None:
    load_dotenv()
    args = parse_args()

    client = Client()
    existing = list(client.list_datasets(dataset_name=args.dataset_name, limit=1))
    if existing and args.replace:
        client.delete_dataset(dataset_id=existing[0].id)

    dataset, created = get_or_create_dataset(client, args.dataset_name)
    examples = load_examples(Path(args.examples_path))

    has_existing = any(client.list_examples(dataset_id=dataset.id, limit=1))
    if has_existing and not args.append and not args.replace:
        print(
            f"Dataset '{dataset.name}' already has examples. "
            "Use --append to add more without skipping, or --replace to recreate it."
        )
        return

    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(
        f"{'Created' if created else 'Updated'} dataset '{dataset.name}' "
        f"with {len(examples)} examples."
    )


if __name__ == "__main__":
    main()
