from __future__ import annotations

import argparse
import json
from typing import Any

from dotenv import load_dotenv
from langsmith import Client, wrappers
from openai import OpenAI

from src.rag.chain import answer_query
from src.storage.repositories import ChunkRepository

_MAX_EVIDENCE_CHARS = 900

_GROUNDEDNESS_JUDGE_PROMPT = """\
You are a strict groundedness evaluator for a RAG system.

Task:
- Decide whether the ANSWER is supported by the provided EVIDENCE only.
- Do not use outside knowledge.
- If the evidence is missing or too weak for one or more claims, penalize.

Return ONLY valid JSON with this schema:
{{
  "label": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED",
  "score": 1.0 | 0.5 | 0.0,
  "reason": "short explanation",
  "unsupported_claims": ["claim 1", "claim 2"]
}}

INPUTS:
{inputs}

OUTPUTS:
{outputs}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run groundedness evaluation in LangSmith."
    )
    parser.add_argument(
        "--dataset-name", default="groundedness-v1", help="LangSmith dataset name."
    )
    parser.add_argument(
        "--experiment-prefix",
        default="groundedness-v1",
        help="Prefix used for the LangSmith experiment run.",
    )
    parser.add_argument(
        "--judge-model", default="gpt-4o-mini", help="OpenAI model used as LLM judge."
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Max concurrent eval calls.",
    )
    return parser.parse_args()


def _serialize_evidence(
    namespace: str, citations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunk_ids = [
        str(c.get("chunk_id", "")).strip() for c in citations if c.get("chunk_id")
    ]
    if not chunk_ids:
        return []

    repo = ChunkRepository(namespace=namespace)
    chunks = repo.fetch_chunks_by_ids(chunk_ids)
    by_id = {chunk.chunk_id: chunk for chunk in chunks}

    evidence: list[dict[str, Any]] = []
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        if not chunk_id:
            continue
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        content = chunk.content.strip()
        evidence.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "page": chunk.page,
                "source_ref": chunk.source_ref,
                "content": content[:_MAX_EVIDENCE_CHARS],
            }
        )
    return evidence


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    question = str(inputs.get("question", "")).strip()
    namespace = str(inputs.get("namespace", "papers")).strip() or "papers"

    result = answer_query(question=question, namespace=namespace)
    citations = [c.model_dump() for c in result.citations]
    evidence = _serialize_evidence(namespace=namespace, citations=citations)
    return {
        "answer": result.answer,
        "citations": citations,
        "evidence": evidence,
    }


def build_groundedness_evaluator(judge_model: str):
    openai_client = wrappers.wrap_openai(OpenAI())

    def groundedness_evaluator(
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        reference_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = reference_outputs  # kept for compatibility with LangSmith evaluator signature
        prompt = _GROUNDEDNESS_JUDGE_PROMPT.format(
            inputs=json.dumps(inputs, ensure_ascii=True),
            outputs=json.dumps(outputs, ensure_ascii=True),
        )
        response = openai_client.chat.completions.create(
            model=judge_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        label = str(parsed.get("label", "UNSUPPORTED")).upper()
        score = float(parsed.get("score", 0.0))
        reason = str(parsed.get("reason", "")).strip()
        unsupported_claims = parsed.get("unsupported_claims", [])

        # LangSmith accepts this schema for custom evaluator feedback.
        return {
            "key": "groundedness",
            "score": score,
            "value": label,
            "comment": reason,
            "metadata": {
                "unsupported_claims": (
                    unsupported_claims if isinstance(unsupported_claims, list) else []
                ),
            },
        }

    return groundedness_evaluator


def main() -> None:
    load_dotenv()
    args = parse_args()

    client = Client()
    groundedness_evaluator = build_groundedness_evaluator(args.judge_model)

    experiment_results = client.evaluate(
        target,
        data=args.dataset_name,
        evaluators=[groundedness_evaluator],
        experiment_prefix=args.experiment_prefix,
        max_concurrency=args.max_concurrency,
    )
    print(experiment_results)


if __name__ == "__main__":
    main()
