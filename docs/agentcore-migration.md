# AgentCore Integration (High-Level)

This MVP is intentionally local-first. When AWS access is available, migrate with minimal architectural changes:

## 1) Replace model provider

- Swap OpenAI chat/embedding/vision clients with Bedrock clients.
- Keep module boundaries unchanged (`ingest`, `retrieval`, `rag`).

## 2) Promote retrieval to tools

- Expose `HybridRetriever.retrieve(query)` as an Agent tool action.
- Expose optional image analysis as a second tool for on-demand visual reasoning.

## 3) Move orchestration to AgentCore

- AgentCore decides:
  - when to retrieve
  - when to call vision analysis
  - how to synthesize final answer

## 4) Add cloud-native runtime concerns

- IAM-scoped permissions for model/tool access
- tracing/logging (CloudWatch + request IDs)
- environment separation (dev/stage/prod)

## 5) Validate parity

- Reuse the same evaluation questions and compare:
  - groundedness
  - citation quality
  - retrieval relevance

Because the current code already separates storage/retrieval/answering, migration is mostly adapter work, not a rewrite.
