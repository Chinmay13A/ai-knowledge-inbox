from dataclasses import dataclass, field

from app.models.chunk import RetrievedChunk


@dataclass(frozen=True)
class Answer:
    """A grounded answer. Source number n (as cited in the text, e.g. [2]) is sources[n - 1]."""

    text: str
    sources: list[RetrievedChunk]
    cited: list[int] = field(default_factory=list)  # 1-based source numbers referenced in `text`
    model_id: str | None = None  # None when no LLM was called (nothing relevant was found)
    truncated: bool = False
