# Architecture

Compact architecture reference with diagram-first documentation and short context for each flow.

## System Overview

End-to-end view of ingestion, storage, retrieval, and answer generation from CLI entrypoints.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
graph TD
    classDef cli        fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef ingest     fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef vision     fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef retrieval  fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold
    classDef storage    fill:#E0E7FF,stroke:#6366F1,color:#312E81,font-weight:bold
    classDef generation fill:#FCE7F3,stroke:#EC4899,color:#500724,font-weight:bold

    subgraph SG1["Terminal"]
        CLI_IP["scripts/ingest.py<br/>papers"]
        CLI_IC["scripts/ingest_cars.py<br/>cars"]
        CLI_DP["scripts/demo.py<br/>Papers chat"]
        CLI_DC["scripts/demo_cars.py<br/>Cars chat"]
    end

    subgraph SG2["Pipeline de Ingestion"]
        DOCLING["Docling Parser<br/>parse_pdf + elementos tipados"]
        CHUNK_P["chunk_elements (papers)<br/>1200 / 150 por elemento"]
        CHUNK_C["chunk_elements_cars (cars)<br/>2400 / 300 por pagina/grupo"]
        VISION["Enriquecimiento Visual<br/>GPT-4o-mini describe figuras y tablas"]
        EMBED["Embeddings<br/>text-embedding-3-small"]
    end

    subgraph SG3["Recuperacion"]
        EXPAND["_expand_query<br/>query original + 2 variantes"]
        LEX["Busqueda Lexica<br/>BM25 via pg_search / fallback tsvector"]
        VEC["Busqueda Vectorial<br/>pgvector coseno / indice HNSW"]
        RRF["RRF Fusion<br/>fusiona resultados de 3 consultas"]
    end

    subgraph SG4["Almacenamiento - ParadeDB / Postgres"]
        DOC_T["documents"]
        CHK_T["chunks<br/>embedding(1536)<br/>content_tsv + bm25"]
    end

    subgraph SG5["Generacion"]
        CHAIN["ReAct Agent (answer_query)<br/>_rewrite_query + loop con tools"]
        TOOL["retrieve tool<br/>fallback sin filter si no hay resultados"]
        LLM["ChatOpenAI gpt-4o-mini<br/>respuesta fundamentada + citas"]
    end

    CLI_IP --> DOCLING
    CLI_IC --> DOCLING
    DOCLING --> CHUNK_P
    DOCLING --> CHUNK_C
    DOCLING --> VISION
    CHUNK_P --> EMBED
    CHUNK_C --> EMBED
    VISION --> CHK_T
    EMBED --> CHK_T
    DOCLING --> DOC_T

    CLI_DP --> CHAIN
    CLI_DC --> CHAIN
    CHAIN --> TOOL
    TOOL --> EXPAND
    EXPAND --> LEX
    EXPAND --> VEC
    LEX --> CHK_T
    VEC --> CHK_T
    LEX --> RRF
    VEC --> RRF
    RRF --> TOOL
    TOOL --> CHAIN
    CHAIN --> LLM

    class CLI_IP,CLI_IC,CLI_DP,CLI_DC cli
    class DOCLING,CHUNK_P,CHUNK_C,EMBED ingest
    class VISION vision
    class EXPAND,LEX,VEC,RRF retrieval
    class DOC_T,CHK_T storage
    class CHAIN,TOOL,LLM generation

    style SG1 fill:#BFDBFE,stroke:#2563EB,color:#000000,font-weight:bold
    style SG2 fill:#A7F3D0,stroke:#059669,color:#000000,font-weight:bold
    style SG3 fill:#FDE68A,stroke:#B45309,color:#000000,font-weight:bold
    style SG4 fill:#C7D2FE,stroke:#4F46E5,color:#000000,font-weight:bold
    style SG5 fill:#FBCFE8,stroke:#DB2777,color:#000000,font-weight:bold
```

## Ingestion

### Papers Ingestion Flow

Scientific papers are parsed into typed elements, chunked by element, enriched with vision descriptions, and stored with embeddings.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io      fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef ingest  fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef vision  fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef storage fill:#E0E7FF,stroke:#6366F1,color:#312E81,font-weight:bold

    ENTRY["scripts/ingest.py"]:::io --> PIPE["pipeline.py<br/>ingest_pdf_papers"]:::ingest
    PDF["📄 papers PDF + metadata.jsonl"]:::io --> PIPE

    PIPE --> PARSER["docling_parser.py<br/>parse_pdf<br/>ParsedElement[]"]:::ingest
    PARSER --> CHUNK["chunking.py<br/>chunk_elements<br/>por elemento (1200/150)"]:::ingest
    PARSER --> EXPORT["image_export.py<br/>export_element_image"]:::vision
    EXPORT --> VISION_E["vision_enrichment.py<br/>build_vision_chunk<br/>GPT-4o-mini"]:::vision

    CHUNK --> REPO["ChunkRepository.upsert_chunks<br/>embeddings text-embedding-3-small"]:::storage
    VISION_E --> REPO
    REPO --> DB[("PostgreSQL<br/>documents + chunks")]:::storage
```

### Cars Ingestion Flow

Car manuals use a dedicated chunking strategy (page/group oriented) to better preserve procedural instructions.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io      fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef ingest  fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef vision  fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef storage fill:#E0E7FF,stroke:#6366F1,color:#312E81,font-weight:bold

    ENTRY_A["scripts/ingest_cars.py"]:::io --> PIPE["pipeline.py<br/>ingest_pdf_cars"]:::ingest
    ENTRY_B["scripts/demo_cars.py<br/>run_chat_session(ingest_fn=ingest_pdf_cars)"]:::io --> PIPE
    PDF["🚗 manual PDF"]:::io --> PIPE

    PIPE --> PARSER["docling_parser.py<br/>parse_pdf<br/>page_images = True"]:::ingest
    PARSER --> CARS_CHUNK["chunking_cars.py<br/>chunk_elements_cars"]:::ingest

    CARS_CHUNK --> GROUP["Agrupa texto por pagina<br/>concatena elementos consecutivos"]:::ingest
    GROUP --> SPLIT["Split recursivo (2400/300)<br/>merge de chunks pequenos"]:::ingest
    PARSER --> TABLES["Tablas como chunk unico"]:::ingest

    SPLIT --> REPO["ChunkRepository.upsert_chunks<br/>embeddings text-embedding-3-small"]:::storage
    TABLES --> REPO
    PARSER --> EXPORT["image_export.py + vision_enrichment.py"]:::vision
    EXPORT --> REPO
    REPO --> DB[("PostgreSQL<br/>documents + chunks")]:::storage
```

## Retrieval

Hybrid retrieval runs lexical and vector search over expanded queries, then fuses all rankings with RRF.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io        fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef hybrid    fill:#E0E7FF,stroke:#6366F1,color:#312E81,font-weight:bold
    classDef expand    fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D,font-weight:bold
    classDef lexical   fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold
    classDef vector    fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef fusion    fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold

    Q["🔍 query"]:::io --> HYBRID

    HYBRID["hybrid.py<br/>HybridRetriever.retrieve"]:::hybrid
    HYBRID --> EXPAND["_expand_query<br/>GPT-4o-mini genera 2 variantes<br/>vocabulario alternativo"]:::expand

    EXPAND --> LEX1["search_lexical<br/>query original"]:::lexical
    EXPAND --> LEX2["search_lexical<br/>variante 1"]:::lexical
    EXPAND --> LEX3["search_lexical<br/>variante 2"]:::lexical
    EXPAND --> VEC1["search_vector<br/>query original"]:::vector
    EXPAND --> VEC2["search_vector<br/>variante 1"]:::vector
    EXPAND --> VEC3["search_vector<br/>variante 2"]:::vector

    LEX1 & LEX2 & LEX3 & VEC1 & VEC2 & VEC3 --> RRF

    RRF["fusion.py<br/>rrf_fuse sobre todos los candidatos<br/>score = Σ 1 / (k + rank)"]:::fusion
    RRF --> OUT["📋 lista de RetrievedChunk<br/>top-8 chunks fusionados"]:::io
```

## RAG Agent

The ReAct loop decides when to call retrieval, accumulates evidence, and returns answer plus citations.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io        fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef chain     fill:#FCE7F3,stroke:#EC4899,color:#500724,font-weight:bold
    classDef retrieval fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold
    classDef llm       fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef agent     fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold

    Q["❓ pregunta + historial"]:::io --> REWRITE

    REWRITE["_rewrite_query<br/>reformula si hay historial<br/>QUERY_REWRITE_PROMPT"]:::chain
    REWRITE --> TOOL

    TOOL["make_retrieve_tool<br/>crea @tool retrieve(query)<br/>acumula en accumulated_chunks"]:::agent
    TOOL --> LOOP

    LOOP["_run_react_loop<br/>llm.bind_tools([retrieve])<br/>max. _MAX_ITER = 5"]:::agent
    LOOP -->|tool_calls| EXEC
    EXEC["retrieve tool<br/>HybridRetriever.retrieve<br/>→ ToolMessage al hilo"]:::retrieval
    EXEC --> LOOP
    LOOP -->|sin tool_calls| DEDUP

    DEDUP["deduplicar accumulated_chunks<br/>por chunk_id"]:::chain
    DEDUP --> OUT["📝 AnswerResult<br/>answer + citations[]"]:::io
```

## Query And Retrieval Loop

Detailed control flow for query rewriting, filtered retrieval, fallback behavior, and iterative tool calls.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef client    fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef chain     fill:#FCE7F3,stroke:#EC4899,color:#500724,font-weight:bold
    classDef retrieval fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold
    classDef llm       fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef fallback  fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D,font-weight:bold

    Q["Cliente: pregunta + historial"]:::client --> ANSWER
    ANSWER["answer_query"]:::chain --> OPT{Hay historial?}
    OPT -->|Si| REWRITE["_rewrite_query + LLM → search_query"]:::chain
    OPT -->|No| LOOP
    REWRITE --> LOOP["_run_react_loop"]
    LOOP --> BIND["LLM con bind_tools(retrieve)"]
    BIND --> TOOL["retrieve tool<br/>normaliza document_filter"]:::retrieval
    TOOL --> HYBRID["HybridRetriever<br/>multi-query fan-out + RRF top-8"]:::retrieval
    HYBRID --> ZERO{0 chunks<br/>con filtro?}
    ZERO -->|No| MSG["ToolMessage con chunks"]:::retrieval
    ZERO -->|Si, fallback| RETRY["reintentar sin document_filter<br/>+ NOTE al LLM"]:::fallback
    RETRY --> MSG
    MSG --> CHECK{Mas tool_calls?}
    CHECK -->|Si, max 5 iter| BIND
    CHECK -->|No| FIN["AIMessage sin tool_calls"]
    FIN --> OUT["AnswerResult con citations"]
    OUT --> CLIENT["Cliente"]:::client

    class LOOP,BIND,CHECK,FIN chain
    class REWRITE llm
```

## Database Schema

Core storage model: `documents` as parent entities and `chunks` as the retrieval unit.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}, 'themeVariables': {
  'primaryColor': '#E0E7FF',
  'primaryBorderColor': '#6366F1',
  'primaryTextColor': '#312E81',
  'lineColor': '#6366F1',
  'secondaryColor': '#DBEAFE',
  'tertiaryColor': '#D1FAE5'
}}}%%
erDiagram
    documents {
        text doc_id PK
        text source_path
        text title
        jsonb authors
        jsonb metadata
    }
    chunks {
        text chunk_id PK
        text doc_id FK
        text content
        text content_type
        int page
        text section
        text source_ref
        text image_path
        jsonb metadata
        vector embedding
        tsvector content_tsv
    }
    documents ||--o{ chunks : "tiene"
```

## Evals

### What we measure and how

- **Groundedness (`scripts/evals/run_groundedness_eval.py`)**: measures whether the generated answer is supported by retrieved evidence only.
- **How groundedness is scored**: the script runs `answer_query`, fetches cited chunks from storage, truncates evidence text, and asks an LLM judge for a strict JSON verdict:
  - `SUPPORTED` -> `1.0`
  - `PARTIALLY_SUPPORTED` -> `0.5`
  - `UNSUPPORTED` -> `0.0`
- **Retrieval coverage (`scripts/evals/run_retrieval_eval.py`)**: measures if retrieved citations contain gold chunks from the dataset labels.
- **How retrieval is scored** (top-k citations, default `k=8`):
  - `retrieval_recall_at_k`: `|predicted ∩ gold| / |gold|`
  - `retrieval_hit_at_k`: `1.0` if at least one gold chunk is in top-k, else `0.0`

### Groundedness Eval Flow

Execution flow from dataset input to LLM-as-judge groundedness feedback in LangSmith.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io         fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef target     fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef storage    fill:#E0E7FF,stroke:#6366F1,color:#312E81,font-weight:bold
    classDef judge      fill:#F3E8FF,stroke:#A855F7,color:#3B0764,font-weight:bold
    classDef metric     fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold

    DS["LangSmith dataset<br/>groundedness-v1"]:::io --> EVAL["client.evaluate(...)"]:::io
    EVAL --> TARGET["target(inputs)"]:::target
    TARGET --> AQ["RAG agent<br/>answer_query(question, namespace)"]:::target
    AQ --> DB["DB lookup<br/>ChunkRepository.fetch_chunks_by_ids(citations)"]:::storage
    DB --> OUT["outputs:<br/>answer + evidence"]:::io
    EVAL --> JUDGE["groundedness_evaluator"]:::judge
    OUT --> JUDGE
    JUDGE --> LLM["LLM judge (gpt-4o-mini)<br/>SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED"]:::judge
    LLM --> METRIC["groundedness score<br/>1.0 / 0.5 / 0.0"]:::metric
```

### Retrieval Eval Flow

Execution flow for `recall@k` and `hit@k` from predicted citations against gold chunk labels.

```mermaid
%%{init: {'theme': 'base', 'securityLevel': 'loose', 'flowchart': {'htmlLabels': true}}}%%
flowchart TD
    classDef io         fill:#DBEAFE,stroke:#3B82F6,color:#1E3A8A,font-weight:bold
    classDef target     fill:#D1FAE5,stroke:#10B981,color:#064E3B,font-weight:bold
    classDef metric     fill:#FEF3C7,stroke:#D97706,color:#78350F,font-weight:bold
    classDef labels     fill:#FCE7F3,stroke:#EC4899,color:#500724,font-weight:bold

    DS["LangSmith dataset<br/>retrieval-v1"]:::io --> EVAL["client.evaluate(...)"]:::io
    IN["inputs: question, namespace"]:::io --> TARGET["target(inputs)"]:::target
    TARGET --> AQ["answer_query(question, namespace)"]:::target
    AQ --> OUT["target outputs:<br/>citations[]"]:::target

    REF["reference_outputs.gold_chunk_ids[]"]:::labels --> GOLD["_gold_chunk_ids(...)"]:::labels
    OUT --> PRED["_predict_chunk_ids(outputs, k)<br/>top-k chunk_id from citations"]:::labels

    PRED --> REC["retrieval_recall_at_k<br/>matched = |predicted ∩ gold|<br/>score = matched / |gold|"]:::metric
    GOLD --> REC

    PRED --> HIT["retrieval_hit_at_k<br/>score = 1.0 if intersection non-empty else 0.0"]:::metric
    GOLD --> HIT

    EVAL --> TARGET
    EVAL --> REC
    EVAL --> HIT
```
