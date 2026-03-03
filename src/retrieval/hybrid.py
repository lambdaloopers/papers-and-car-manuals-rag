from __future__ import annotations

from openai import OpenAI

from src.config import get_settings
from src.domain.models import RetrievedChunk
from src.retrieval.fusion import rrf_fuse
from src.retrieval.lexical import search_lexical
from src.retrieval.vector import search_vector

_QUERY_EXPANSION_PROMPT = """\
Given the search query below, write {n} alternative phrasings that use different \
vocabulary but capture the same information need. Use synonyms and related technical \
terms a document might actually contain. Output only the alternatives, one per line, \
no numbering, no explanation.

Query: {query}"""


def _expand_query(query: str, n: int = 2) -> list[str]:
    """Return n alternative phrasings for query using the chat model."""
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _QUERY_EXPANSION_PROMPT.format(n=n, query=query)
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=128,
    )
    raw = response.choices[0].message.content or ""
    alternatives = [line.strip() for line in raw.splitlines() if line.strip()]
    return alternatives[:n]


class HybridRetriever:
    def __init__(self, namespace: str = "papers") -> None:
        self.settings = get_settings()
        self._namespace = namespace

    def _search_one(
        self, query: str, document_filter: str | None
    ) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
        lexical = search_lexical(
            query=query,
            k=self.settings.retrieval_k_lexical,
            namespace=self._namespace,
            document_filter=document_filter,
        )
        vector = search_vector(
            query=query,
            k=self.settings.retrieval_k_vector,
            namespace=self._namespace,
            document_filter=document_filter,
        )
        return lexical, vector

    def retrieve(
        self,
        query: str,
        document_filter: str | None = None,
    ) -> list[RetrievedChunk]:
        # Collect candidates from the original query and two expanded variants.
        all_lexical: list[RetrievedChunk] = []
        all_vector: list[RetrievedChunk] = []

        for q in [query] + _expand_query(query, n=2):
            lex, vec = self._search_one(q, document_filter)
            all_lexical.extend(lex)
            all_vector.extend(vec)

        return rrf_fuse(
            lexical_results=all_lexical,
            vector_results=all_vector,
            k=self.settings.retrieval_k_final,
            rrf_k=self.settings.rrf_k,
        )
