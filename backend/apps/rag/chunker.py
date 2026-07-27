"""Sentence-aware chunking with overlap.

Splitting mid-sentence is the cheapest way to ruin retrieval quality, so
chunks are assembled from whole sentences up to a token budget.
"""
from __future__ import annotations

import re

SENTENCE = re.compile(r"(?<=[.!?])\s+")


def chunk(text: str, max_chars: int = 900, overlap_sentences: int = 1) -> list[str]:
    sentences = [s.strip() for s in SENTENCE.split(text.strip()) if s.strip()]
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        if size + len(sentence) > max_chars and current:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences else []
            size = sum(len(s) for s in current)
        current.append(sentence)
        size += len(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks
