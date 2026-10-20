"""Request/response models: the public API contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.item import Item, ItemStatus, SourceType

MAX_NOTE_CHARS = 50_000
PREVIEW_CHARS = 200


class NoteIngestRequest(BaseModel):
    type: Literal["note"]
    content: str = Field(description="Plain-text note", examples=["Meeting notes: ship v1 by Friday"])

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        if len(value) > MAX_NOTE_CHARS:
            raise ValueError(f"must be at most {MAX_NOTE_CHARS} characters")
        return value


class UrlIngestRequest(BaseModel):
    type: Literal["url"]
    url: HttpUrl = Field(examples=["https://en.wikipedia.org/wiki/Retrieval-augmented_generation"])


IngestRequest = Annotated[NoteIngestRequest | UrlIngestRequest, Field(discriminator="type")]


class ItemOut(BaseModel):
    id: int
    source_type: SourceType
    title: str
    url: str | None
    status: ItemStatus
    created_at: str
    preview: str

    @classmethod
    def from_item(cls, item: Item) -> "ItemOut":
        return cls(
            id=item.id,
            source_type=item.source_type,
            title=item.title,
            url=item.url,
            status=item.status,
            created_at=item.created_at,
            preview=item.content[:PREVIEW_CHARS],
        )


class ItemListResponse(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int
