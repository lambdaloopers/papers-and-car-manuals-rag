from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langsmith import traceable

from src.config import get_settings
from src.domain.models import AnswerResult, Citation, RetrievedChunk
from src.rag.prompts import PAPERS_SYSTEM_PROMPT, QUERY_REWRITE_PROMPT
from src.retrieval.hybrid import HybridRetriever

_MAX_HISTORY_TURNS = 10  # turns fed to query rewriter
_MAX_ITER = 5  # ReAct loop guard


def make_retrieve_tool(namespace: str, accumulated_chunks: list[RetrievedChunk]):
    retriever = HybridRetriever(namespace=namespace)

    @tool
    def retrieve(query: str, document_filter: str | None = None) -> str:
        """Search the document corpus with a natural-language query and return relevant chunks.
        Use document_filter when the user asks about a specific document, paper, or manual
        (e.g. a paper title or car model name) so that only chunks from that document are returned."""
        chunks = retriever.retrieve(query, document_filter=document_filter)

        # If a filter was applied but returned nothing, broaden to the whole corpus
        # and signal this to the LLM so it can adjust its answer.
        fallback_note = ""
        if document_filter and not chunks:
            chunks = retriever.retrieve(query, document_filter=None)
            if chunks:
                fallback_note = (
                    f"NOTE: No chunks found for document_filter='{document_filter}'. "
                    "Results below are from the full corpus.\n\n"
                )

        accumulated_chunks.extend(chunks)
        if not chunks:
            return "No relevant chunks found."
        lines: list[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            lines.append(
                f"[{idx}] doc_id={chunk.doc_id} chunk_id={chunk.chunk_id} "
                f"paper_title={chunk.paper_title} type={chunk.content_type} "
                f"page={chunk.page} source_ref={chunk.source_ref}\n"
                f"{chunk.content}"
            )
        return fallback_note + "\n\n".join(lines)

    return retrieve


@traceable(name="rewrite_query")
def _rewrite_query(question: str, conversation_history: list[dict[str, str]], llm: ChatOpenAI) -> str:
    history_turns = conversation_history[-_MAX_HISTORY_TURNS:]
    history_text = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history_turns)
    prompt = QUERY_REWRITE_PROMPT.format(history=history_text, question=question)
    result = llm.invoke([HumanMessage(content=prompt)])
    rewritten = str(result.content).strip()
    return rewritten if rewritten else question


def _run_react_loop(messages: list, llm_with_tools, retrieve_tool) -> str:
    for _ in range(_MAX_ITER):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            return str(response.content)
        for tc in response.tool_calls:
            output = retrieve_tool.invoke(tc["args"])
            messages.append(ToolMessage(content=output, tool_call_id=tc["id"]))
    # exhausted: one final synthesis call
    return str(llm_with_tools.invoke(messages).content)


@traceable(name="answer_query")
def answer_query(
    question: str,
    namespace: str = "papers",
    conversation_history: list[dict[str, str]] | None = None,
    system_prompt: str = PAPERS_SYSTEM_PROMPT,
) -> AnswerResult:
    settings = get_settings()
    llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_chat_model, temperature=0)

    history = conversation_history or []
    search_query = _rewrite_query(question, history, llm) if history else question

    accumulated_chunks: list[RetrievedChunk] = []
    retrieve_tool = make_retrieve_tool(namespace, accumulated_chunks)

    messages: list = [SystemMessage(content=system_prompt)]
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))
    messages.append(HumanMessage(content=search_query))

    answer = _run_react_loop(messages, llm.bind_tools([retrieve_tool]), retrieve_tool)

    # Deduplicate by chunk_id (preserve insertion order)
    seen: dict[str, RetrievedChunk] = {}
    for chunk in accumulated_chunks:
        if chunk.chunk_id not in seen:
            seen[chunk.chunk_id] = chunk

    citations = [
        Citation(
            doc_id=chunk.doc_id,
            paper_title=chunk.paper_title,
            chunk_id=chunk.chunk_id,
            content_type=chunk.content_type,
            page=chunk.page,
            source_ref=chunk.source_ref,
        )
        for chunk in seen.values()
    ]
    return AnswerResult(answer=answer, citations=citations)
