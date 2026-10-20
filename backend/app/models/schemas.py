"""Request/response models: the public API contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.answer import Answer
from app.models.chunk import RetrievedChunk
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
    error: str | None = Field(default=None, description="Why processing failed (only when status is 'failed')")
    created_at: str
    chunk_count: int
    preview: str

    @classmethod
    def from_item(cls, item: Item) -> "ItemOut":
        return cls(
            id=item.id,
            source_type=item.source_type,
            title=item.title,
            url=item.url,
            status=item.status,
            error=item.error if item.status == "failed" else None,
            created_at=item.created_at,
            chunk_count=item.chunk_count,
            preview=item.content[:PREVIEW_CHARS],
        )


class ItemListResponse(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int


class ChunkOut(BaseModel):
    index: int
    text: str
    chars: int


class ItemChunksResponse(BaseModel):
    item_id: int
    chunks: list[ChunkOut]


MAX_QUERY_CHARS = 1_000


class SearchRequest(BaseModel):
    query: str = Field(examples=["What is retrieval-augmented generation?"])
    top_k: int | None = Field(default=None, ge=1, le=20, description="Defaults to RETRIEVAL_TOP_K")

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        return _clean_question(value)


class SearchResult(BaseModel):
    item_id: int
    item_title: str
    item_url: str | None
    source_type: SourceType
    chunk_index: int
    text: str
    score: float

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> "SearchResult":
        return cls(
            item_id=chunk.item_id,
            item_title=chunk.item_title,
            item_url=chunk.item_url,
            source_type=chunk.source_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            score=round(chunk.score, 4),
        )


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class QueryRequest(BaseModel):
    question: str = Field(examples=["What is retrieval-augmented generation?"])
    top_k: int | None = Field(default=None, ge=1, le=20, description="Defaults to RETRIEVAL_TOP_K")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        return _clean_question(value)


class QuerySource(BaseModel):
    id: int = Field(description="The number used in the answer's [n] citations")
    cited: bool = Field(description="Whether the answer cites this source")
    item_id: int
    item_title: str
    item_url: str | None
    source_type: SourceType
    chunk_index: int
    snippet: str
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[QuerySource]
    model: str | None = Field(description="LLM that wrote the answer; null if nothing relevant was found")
    truncated: bool = Field(description="True if the answer hit the output token limit")

    @classmethod
    def from_answer(cls, question: str, answer: Answer) -> "QueryResponse":
        return cls(
            question=question,
            answer=answer.text,
            sources=[
                QuerySource(
                    id=number,
                    cited=number in answer.cited,
                    item_id=chunk.item_id,
                    item_title=chunk.item_title,
                    item_url=chunk.item_url,
                    source_type=chunk.source_type,
                    chunk_index=chunk.chunk_index,
                    snippet=chunk.text,
                    score=round(chunk.score, 4),
                )
                for number, chunk in enumerate(answer.sources, start=1)
            ],
            model=answer.model_id,
            truncated=answer.truncated,
        )


def _clean_question(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    if len(value) > MAX_QUERY_CHARS:
        raise ValueError(f"must be at most {MAX_QUERY_CHARS} characters")
    return value
