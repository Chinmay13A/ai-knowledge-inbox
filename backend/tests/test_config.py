import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(("size", "overlap"), [(800, 400), (800, -1), (50, 0)])
def test_invalid_chunking_settings_fail_fast(size: int, overlap: int) -> None:
    with pytest.raises(ValidationError, match="CHUNK_"):
        Settings(chunk_size_chars=size, chunk_overlap_chars=overlap)


def test_chunking_config_comes_from_settings() -> None:
    settings = Settings(chunk_size_chars=500, chunk_overlap_chars=50)

    assert (settings.chunking.size, settings.chunking.overlap) == (500, 50)
