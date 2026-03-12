# Local Multimodal RAG MVP

Local-first multimodal RAG for any PDF collection using:
- Docling for PDF structuring and image extraction
- OpenAI models for embeddings, chat, and vision captioning
- Postgres (Docker) with `pg_search` BM25 and `pgvector` semantic retrieval
- LangChain for orchestration

Each document collection (e.g. `papers`, `cars`) lives in its own Postgres schema, giving full isolation of documents, chunks, and indexes.

## 1) Prerequisites

- Python 3.11+
- Docker Desktop
- OpenAI API key

## 2) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`.

## 3) Start database

```bash
docker compose up -d
```

## 4) Start a chat session

Each demo script auto-ingests on first run, then drops into an interactive chat. Conversation history is maintained across turns so you can ask follow-up questions.

### arXiv papers

Put PDFs in `./data/arxiv_recent` (or download them first):

```bash
PYTHONPATH=. python scripts/download_arxiv_recent.py --max-results 30  # optional
PYTHONPATH=. python scripts/demo.py
```

### Car manuals

Put PDFs in `./data/car_manuals`, then:

```bash
PYTHONPATH=. python scripts/demo_cars.py
```

Both scripts accept:

| Flag | Default | Description |
|---|---|---|
| `--input-dir` | mode-specific | Directory with PDFs to ingest on first run |
| `--namespace` | `papers` / `cars` | Postgres schema for this collection |
| `--force-ingest` | off | Re-ingest even if data already exists |

Each namespace gets its own `documents` and `chunks` tables created automatically. Ingest runs Docling parse → image export → vision captioning → chunk embedding.

### Manual ingest (optional)

If you want to ingest without starting a chat session:

```bash
PYTHONPATH=. python scripts/ingest.py --input-dir ./data/arxiv_recent --namespace papers
PYTHONPATH=. python scripts/ingest.py --input-dir ./data/car_manuals --namespace cars
```

## Clean code conventions used

- Domain models in `src/domain`
- DB concerns isolated in `src/storage`
- Pure ranking logic in `src/retrieval/fusion.py`
- Centralized settings in `src/config.py`
- Namespace isolation via Postgres schemas (`papers.*`, `cars.*`)

## Notes

- Lexical retrieval tries ParadeDB BM25 first and falls back to Postgres FTS if needed.
- Vision captions are stored as extra chunks (`figure_caption` / `table_caption`) so multimodal evidence participates in retrieval.

## Evals (LangSmith SDK)

This repo includes two evaluators with separate datasets:

- groundedness evaluator (faithfulness to retrieved evidence)
- retrieval evaluator (Recall/Hit at K against gold chunk IDs)

Prerequisites:

- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY`
- `OPENAI_API_KEY`

Run:

```bash
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name groundedness-v1
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name retrieval-v1 --examples-path ./data/evals/retrieval_examples.jsonl
PYTHONPATH=. python scripts/evals/run_groundedness_eval.py --dataset-name groundedness-v1 --experiment-prefix groundedness-v1
PYTHONPATH=. python scripts/evals/run_retrieval_eval.py --dataset-name retrieval-v1 --experiment-prefix retrieval-v1 --k 8
```

To replace an existing LangSmith dataset instead of appending:

```bash
PYTHONPATH=. python scripts/evals/create_groundedness_dataset.py --dataset-name groundedness-v1 --replace
```

More details: `docs/evals-groundedness.md`
