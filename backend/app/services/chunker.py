"""Splits text into overlapping, structure-aware chunks for embedding and retrieval.

Strategy: keep paragraphs whole when they fit, otherwise split them at sentence
boundaries (then word boundaries), greedily pack the pieces into chunks of at most
`size` characters, and start each chunk with a short tail of the previous one.
Pure functions only: no I/O, fully deterministic.
"""

import re
from dataclasses import dataclass

from app.models.chunk import Chunk

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_INLINE_WHITESPACE = re.compile(r"[^\S\n]+")  # any whitespace except newlines (incl. non-breaking space)


@dataclass(frozen=True)
class _Unit:
    text: str
    starts_block: bool  # True if this unit begins a new paragraph/line


def chunk_text(text: str, *, size: int = 800, overlap: int = 100) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("size must be positive and 0 <= overlap < size")

    # Units leave room for the overlap tail plus one separator, so no chunk exceeds `size`.
    unit_limit = size - overlap - 1 if overlap else size
    units = [unit for block in _blocks(text) for unit in _split_block(block, unit_limit)]

    chunks: list[str] = []
    current = ""
    for unit in units:
        separator = "\n" if unit.starts_block else " "
        if current and len(current) + len(separator) + len(unit.text) <= size:
            current += separator + unit.text
            continue
        if current:
            chunks.append(current)
            tail = _tail(current, overlap)
            current = f"{tail}{separator}{unit.text}" if tail else unit.text
        else:
            current = unit.text
    if current:
        chunks.append(current)

    return [Chunk(index=i, text=chunk) for i, chunk in enumerate(chunks)]


def _blocks(text: str) -> list[str]:
    """Normalized, non-empty lines: paragraphs, list items and headings."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned = (_INLINE_WHITESPACE.sub(" ", line).strip() for line in lines)
    return [line for line in cleaned if line]


def _split_block(block: str, limit: int) -> list[_Unit]:
    if len(block) <= limit:
        pieces = [block]
    else:
        pieces = []
        for sentence in _SENTENCE_BOUNDARY.split(block):
            pieces.extend([sentence] if len(sentence) <= limit else _split_words(sentence, limit))
    return [_Unit(text=piece, starts_block=i == 0) for i, piece in enumerate(pieces)]


def _split_words(sentence: str, limit: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in sentence.split(" "):
        while len(word) > limit:  # a single "word" longer than a chunk (e.g. a long URL)
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:limit])
            word = word[limit:]
        if current and len(current) + 1 + len(word) > limit:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """Last <= `overlap` characters of `text`, starting at a word boundary."""
    if overlap == 0:
        return ""
    if len(text) <= overlap:
        return text
    tail = text[-overlap:]
    if not text[-overlap - 1].isspace():
        # Drop the partial first word; if there is no whitespace, there is no clean tail.
        parts = re.split(r"\s", tail, maxsplit=1)
        tail = parts[1] if len(parts) == 2 else ""
    return tail.strip()
