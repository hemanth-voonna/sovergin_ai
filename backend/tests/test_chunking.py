"""Chunker tests."""
from __future__ import annotations

from rag.chunker import chunk_pages, chunk_text


def test_chunk_text_short_text_no_split():
    assert chunk_text("short text", chunk_size=900) == ["short text"]


def test_chunk_text_splits_with_overlap():
    text = "word " * 500  # 2500 chars
    chunks = chunk_text(text, chunk_size=900, overlap=120)
    assert len(chunks) >= 3
    assert all(len(c) <= 950 for c in chunks)
    # overlap present between consecutive chunks
    assert chunks[0][-60:] in chunks[1] or chunks[1][:60] in chunks[0]


def test_chunk_text_empty():
    assert chunk_text("   ") == []
    assert chunk_text("") == []


def test_chunk_pages_tracks_page_numbers():
    chunks = chunk_pages([(1, "one " * 300), (2, "two " * 300)], chunk_size=500, overlap=50)
    assert any(c.page == 1 for c in chunks)
    assert any(c.page == 2 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_pages_rejects_control_chars():
    text = "clean text\x00with nulls\x00"
    chunks = chunk_text(text)
    assert "\x00" not in chunks[0]