import sqlite3
from dataclasses import dataclass
from typing import Literal

SourceType = Literal["note", "url"]
ItemStatus = Literal["pending", "ready", "failed"]


@dataclass(frozen=True)
class Item:
    """A saved note or URL, as stored in the database."""

    id: int
    source_type: SourceType
    title: str
    url: str | None
    content: str
    status: ItemStatus
    error: str | None
    created_at: str
    chunk_count: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Item":
        return cls(**{key: row[key] for key in row.keys()})  # noqa: SIM118 - iterating a Row yields values
