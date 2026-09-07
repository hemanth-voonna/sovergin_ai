"""Chunking: split documents into overlapping, page-aware chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings


@dataclass
class Chunk:
    text: str
    page: int | None = None
    chunk_index: int = 0
    chunk_id: str = ""

    def to_dict(self) -> dict:
        return {"text": self.text, "page": self.page, "chunk_index": self.chunk_index}


def _clean_for_chunk(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int | None = None,
               overlap: int | None = None) -> list[str]:
    """Split a single blob of text into overlapping chunks."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    text = _clean_for_chunk(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            # try to break on sentence / newline boundaries
            window = text[start:end]
            for sep in ("\n", ". ", ".", " "):
                idx = window.rfind(sep)
                if idx > chunk_size * 0.5:
                    end = start + idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int | None = None,
                overlap: int | None = None) -> list[Chunk]:
    """Chunk page-wise so every chunk keeps its page number."""
    chunks: list[Chunk] = []
    idx = 0
    for page_number, text in pages:
        for piece in chunk_text(text, chunk_size, overlap):
            chunks.append(
                Chunk(text=piece, page=page_number, chunk_index=idx, chunk_id="")
            )
            idx += 1
    return chunks