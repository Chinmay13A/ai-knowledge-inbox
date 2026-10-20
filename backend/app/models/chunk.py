import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    size: int = 800  # max characters per chunk
    overlap: int = 100  # characters repeated from the end of the previous chunk


@dataclass(frozen=True)
class Chunk:
    """A piece of text produced by the chunker, before it is stored."""

    index: int
    text: str


@dataclass(frozen=True)
class StoredChunk:
    """A chunk of an item's text, as stored in the database."""

    id: int
    item_id: int
    chunk_index: int
    text: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredChunk":
        return cls(id=row["id"], item_id=row["item_id"], chunk_index=row["chunk_index"], text=row["text"])
