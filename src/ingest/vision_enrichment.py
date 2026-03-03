from __future__ import annotations

import base64
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.domain.models import ChunkRecord


def _encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def _describe_image(client: OpenAI, image_path: Path) -> str:
    settings = get_settings()
    image_b64 = _encode_image(image_path)
    response = client.responses.create(
        model=settings.openai_vision_model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Describe this scientific figure or table for retrieval in a RAG system. "
                            "Focus on key findings, variables, trends, and labels in 120 words max."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}",
                    },
                ],
            }
        ],
        max_output_tokens=220,
    )
    return response.output_text.strip()


def build_vision_chunk(
    *,
    chunk_id: str,
    doc_id: str,
    image_path: Path,
    page: int | None,
    source_ref: str | None,
    content_type: str,
) -> ChunkRecord:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    caption = _describe_image(client, image_path)

    target_type = "figure_caption" if content_type == "figure" else "table_caption"
    return ChunkRecord(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=caption,
        content_type=target_type,  # type: ignore[arg-type]
        page=page,
        source_ref=source_ref,
        image_path=str(image_path),
        metadata={"generated_by": settings.openai_vision_model, "origin": content_type},
    )
