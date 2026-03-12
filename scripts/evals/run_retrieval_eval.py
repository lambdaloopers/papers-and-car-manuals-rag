from __future__ import annotations

import argparse
from typing import Any

from dotenv import load_dotenv
from langsmith import Client

from src.rag.chain import answer_query


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval coverage evaluation in LangSmith.")
    parser.add_argument("--dataset-name", default="retrieval-v1", help="LangSmith dataset name.")
    parser.add_argument(
        "--experiment-prefix",
        default="retrieval-v1",
        help="Prefix used for the LangSmith experiment run.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=8,
        help="Top-k citations to evaluate for recall/hit metrics.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Max concurrent eval calls.",
    )
    return parser.parse_args()


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    question = str(inputs.get("question", "")).strip()
    namespace = str(inputs.get("namespace", "papers")).strip() or "papers"

    result = answer_query(question=question, namespace=namespace)
    citations = [c.model_dump() for c in result.citations]
    return {"citations": citations}


def _predict_chunk_ids(outputs: dict[str, Any], k: int) -> list[str]:
    citations = outputs.get("citations") or []
    if not isinstance(citations, list):
        return []
    predicted: list[str] = []
    for item in citations[:k]:
        if not isinstance(item, dict):
            continue
        chunk_id = item.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id.strip():
            predicted.append(chunk_id.strip())
    return predicted


def _gold_chunk_ids(reference_outputs: dict[str, Any] | None) -> list[str]:
    if not isinstance(reference_outputs, dict):
        return []
    gold = reference_outputs.get("gold_chunk_ids") or []
    if not isinstance(gold, list):
        return []
    return [item.strip() for item in gold if isinstance(item, str) and item.strip()]


def build_retrieval_recall_evaluator(k: int):
    key = f"retrieval_recall_at_{k}"

    def retrieval_recall_evaluator(
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        reference_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = inputs
        predicted = set(_predict_chunk_ids(outputs, k))
        gold = set(_gold_chunk_ids(reference_outputs))
        if not gold:
            return {
                "key": key,
                "score": 0.0,
                "value": "MISSING_GOLD_LABELS",
                "comment": "No gold_chunk_ids in reference outputs for this example.",
            }
        matched = len(predicted.intersection(gold))
        recall = matched / len(gold)
        return {
            "key": key,
            "score": float(recall),
            "value": f"{matched}/{len(gold)}",
            "comment": f"Matched {matched} gold chunks in top-{k} citations.",
        }

    return retrieval_recall_evaluator


def build_retrieval_hit_evaluator(k: int):
    key = f"retrieval_hit_at_{k}"

    def retrieval_hit_evaluator(
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        reference_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = inputs
        predicted = set(_predict_chunk_ids(outputs, k))
        gold = set(_gold_chunk_ids(reference_outputs))
        if not gold:
            return {
                "key": key,
                "score": 0.0,
                "value": "MISSING_GOLD_LABELS",
                "comment": "No gold_chunk_ids in reference outputs for this example.",
            }
        hit = 1.0 if predicted.intersection(gold) else 0.0
        return {
            "key": key,
            "score": hit,
            "value": "HIT" if hit == 1.0 else "MISS",
            "comment": f"Top-{k} citations {'contain' if hit == 1.0 else 'do not contain'} any gold chunk.",
        }

    return retrieval_hit_evaluator


def main() -> None:
    load_dotenv()
    args = parse_args()

    client = Client()
    retrieval_recall_evaluator = build_retrieval_recall_evaluator(args.k)
    retrieval_hit_evaluator = build_retrieval_hit_evaluator(args.k)

    experiment_results = client.evaluate(
        target,
        data=args.dataset_name,
        evaluators=[retrieval_recall_evaluator, retrieval_hit_evaluator],
        experiment_prefix=args.experiment_prefix,
        max_concurrency=args.max_concurrency,
    )
    print(experiment_results)


if __name__ == "__main__":
    main()
