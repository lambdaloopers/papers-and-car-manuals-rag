from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.domain.types import ContentType


class DocumentRecord(BaseModel):
    doc_id: str
    source_path: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkRecord(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    content_type: ContentType
    page: int | None = None
    section: str | None = None
    source_ref: str | None = None
    image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    paper_title: str | None = None
    content: str
    content_type: ContentType
    score: float
    page: int | None = None
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    doc_id: str
    paper_title: str | None = None
    chunk_id: str
    content_type: ContentType
    page: int | None = None
    source_ref: str | None = None


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
