import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(("size", "overlap"), [(800, 400), (800, -1), (50, 0)])
def test_invalid_chunking_settings_fail_fast(size: int, overlap: int) -> None:
    with pytest.raises(ValidationError, match="CHUNK_"):
        Settings(_env_file=None, chunk_size_chars=size, chunk_overlap_chars=overlap)


def test_chunking_config_comes_from_settings() -> None:
    settings = Settings(_env_file=None, chunk_size_chars=500, chunk_overlap_chars=50)

    assert (settings.chunking.size, settings.chunking.overlap) == (500, 50)


@pytest.mark.parametrize(("top_k", "min_score"), [(0, 0.5), (21, 0.5), (5, 1.5), (5, -2.0)])
def test_invalid_retrieval_settings_fail_fast(top_k: int, min_score: float) -> None:
    with pytest.raises(ValidationError, match="RETRIEVAL_"):
        Settings(_env_file=None, retrieval_top_k=top_k, retrieval_min_score=min_score)
