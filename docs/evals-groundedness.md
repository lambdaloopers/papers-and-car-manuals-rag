# Groundedness Evaluator (LangSmith SDK)

This project includes two evaluators with separate LangSmith datasets:

- groundedness (LLM-as-judge, evidence faithfulness)
- retrieval coverage (deterministic Recall/Hit over gold chunk IDs)

## What this evaluates

- **Evaluator name:** `groundedness`
- **Domains:** `papers` and `cars`
- **Question answered:** "Is the answer supported by retrieved evidence chunks?"
- **Labels:** `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`
- **Scores:** `1.0`, `0.5`, `0.0`

## Retrieval coverage metrics

- **Script:** `scripts/evals/run_retrieval_eval.py`
- **Metrics:** `retrieval_recall_at_k`, `retrieval_hit_at_k`
- **Question answered:** "Did top-k retrieved citations include expected evidence chunks?"
- **Gold labels source:** `outputs.gold_chunk_ids` in dataset examples

## Files

- Groundedness dataset seed: `data/evals/groundedness_examples.jsonl`
- Retrieval dataset seed: `data/evals/retrieval_examples.jsonl`
- Dataset creation script: `scripts/evals/create_groundedness_dataset.py`
- Groundedness runner: `scripts/evals/run_groundedness_eval.py`
- Retrieval runner: `scripts/evals/run_retrieval_eval.py`

## Environment setup

Required variables:

- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_TRACING=true`
- optional: `LANGSMITH_WORKSPACE_ID` (if your key belongs to multiple workspaces)

Example:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="<your-langsmith-api-key>"
export OPENAI_API_KEY="<your-openai-api-key>"
```

## Run

1) Create or update groundedness dataset in LangSmith:

```bash
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name groundedness-v1
```

1) Create or update retrieval dataset in LangSmith:

```bash
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name retrieval-v1 --examples-path ./data/evals/retrieval_examples.jsonl
```

To fully replace an existing dataset with the same name:

```bash
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name groundedness-v1 --replace
```

1) Run groundedness experiment:

```bash
PYTHONPATH=. python scripts/evals/run_groundedness_eval.py --dataset-name groundedness-v1 --experiment-prefix groundedness-v1
```

1) Run retrieval coverage experiment:

```bash
PYTHONPATH=. python scripts/evals/run_retrieval_eval.py --dataset-name retrieval-v1 --experiment-prefix retrieval-v1 --k 8
```

Each command prints experiment metadata and a LangSmith link to inspect per-example runs and scores.

## Scoring policy for v1 demo

- Target average groundedness score: **>= 0.85**
- Additional safety gate: **no `UNSUPPORTED`** on safety-critical `cars` examples

## How evidence is assembled

The target function calls `answer_query(...)`, then:

1. serializes citations from `AnswerResult`
2. loads corresponding chunks by `chunk_id`
3. passes `answer + evidence` to the judge model

Evidence text is truncated to keep judge context size bounded.

## Current limitations

- This evaluator checks faithfulness to retrieved evidence, not retrieval recall.
- Judge quality can vary by model; use deterministic settings (`temperature=0`) for reproducibility.
- v1 dataset is intentionally small and should be expanded before using as a release gate.

## Dataset labeling for retrieval

For examples that should contribute to retrieval metrics, add:

- `outputs.gold_chunk_ids`: list of expected chunk IDs
- optional `outputs.gold_source_refs`: list of expected source refs

Examples without `gold_chunk_ids` are treated as unlabeled for retrieval quality.
