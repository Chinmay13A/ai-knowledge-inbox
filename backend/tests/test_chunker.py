import random

import pytest

from app.services.chunker import chunk_text

SENTENCE = "Retrieval-augmented generation grounds model answers in retrieved documents."


def paragraph(sentences: int, seed: int = 0) -> str:
    rng = random.Random(seed)
    words = ["vector", "embedding", "chunk", "query", "context", "answer", "source", "model", "index"]
    return " ".join(
        " ".join(rng.choice(words) for _ in range(rng.randint(6, 18))).capitalize() + "."
        for _ in range(sentences)
    )


def assert_invariants(text: str, size: int, overlap: int) -> None:
    chunks = chunk_text(text, size=size, overlap=overlap)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.text.strip() for c in chunks), "no empty chunks"
    assert all(len(c.text) <= size for c in chunks), max(len(c.text) for c in chunks)


class TestBasics:
    @pytest.mark.parametrize("text", ["", "   ", "\n\n \t \n"])
    def test_blank_text_has_no_chunks(self, text: str) -> None:
        assert chunk_text(text) == []

    def test_short_text_is_one_chunk(self) -> None:
        chunks = chunk_text("Buy milk.\nCall the bank.")

        assert len(chunks) == 1
        assert chunks[0].text == "Buy milk.\nCall the bank."

    def test_whitespace_is_normalized(self) -> None:
        chunks = chunk_text("  First   line\r\n\r\n\r\nSecond\tline here  ")

        assert chunks[0].text == "First line\nSecond line here"

    def test_is_deterministic(self) -> None:
        text = "\n".join(paragraph(8, seed) for seed in range(5))

        assert chunk_text(text) == chunk_text(text)

    @pytest.mark.parametrize(("size", "overlap"), [(0, 0), (100, 100), (100, -1)])
    def test_invalid_parameters(self, size: int, overlap: int) -> None:
        with pytest.raises(ValueError):
            chunk_text("text", size=size, overlap=overlap)


class TestSplitting:
    def test_short_paragraphs_are_packed_together(self) -> None:
        paragraphs = [f"Paragraph {i}. {SENTENCE}" for i in range(6)]  # ~90 chars each

        chunks = chunk_text("\n".join(paragraphs), size=300, overlap=0)

        assert len(chunks) == 2
        assert chunks[0].text.split("\n") == paragraphs[:3]

    def test_paragraph_that_fits_is_never_split(self) -> None:
        paragraphs = [paragraph(3, seed) for seed in range(6)]
        assert all(len(p) < 300 for p in paragraphs)

        chunks = chunk_text("\n".join(paragraphs), size=400, overlap=0)

        for p in paragraphs:
            assert any(p in c.text for c in chunks)

    def test_long_paragraph_splits_at_sentence_boundaries(self) -> None:
        text = " ".join(f"Sentence number {i} talks about retrieval." for i in range(40))

        chunks = chunk_text(text, size=200, overlap=0)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.text.startswith("Sentence number")
            assert chunk.text.endswith("retrieval.")

    def test_giant_sentence_splits_at_word_boundaries(self) -> None:
        words = [f"word{i}" for i in range(300)]

        chunks = chunk_text(" ".join(words), size=200, overlap=0)

        assert len(chunks) > 1
        rejoined = " ".join(c.text for c in chunks).split(" ")
        assert rejoined == words  # no word was cut in half

    def test_single_huge_token_is_hard_cut(self) -> None:
        url = "https://example.com/" + "a" * 1_000

        chunks = chunk_text(url, size=200, overlap=0)

        assert "".join(c.text for c in chunks) == url
        assert all(len(c.text) <= 200 for c in chunks)


class TestOverlap:
    def test_next_chunk_starts_with_tail_of_previous(self) -> None:
        text = " ".join(f"Fact {i} is stated in this sentence." for i in range(60))

        chunks = chunk_text(text, size=300, overlap=60)

        assert len(chunks) > 2
        for previous, current in zip(chunks, chunks[1:]):
            first_line_words = current.text.split()[:3]
            assert " ".join(first_line_words) in previous.text[-80:]

    def test_zero_overlap_shares_no_text(self) -> None:
        text = " ".join(f"Fact {i} is stated in this sentence." for i in range(60))

        chunks = chunk_text(text, size=300, overlap=0)

        assert " ".join(c.text for c in chunks) == text

    def test_overlap_starts_at_a_word_boundary(self) -> None:
        text = " ".join(f"alpha{i}" for i in range(200))

        chunks = chunk_text(text, size=150, overlap=40)

        for chunk in chunks[1:]:
            assert chunk.text.split(" ")[0].startswith("alpha")


@pytest.mark.parametrize(("size", "overlap"), [(800, 100), (300, 50), (120, 0), (500, 200)])
@pytest.mark.parametrize("seed", range(5))
def test_invariants_hold_for_mixed_text(size: int, overlap: int, seed: int) -> None:
    rng = random.Random(seed)
    blocks = []
    for i in range(rng.randint(5, 25)):
        kind = rng.choice(["heading", "short", "long", "giant"])
        if kind == "heading":
            blocks.append(f"Section {i}")
        elif kind == "short":
            blocks.append(paragraph(2, seed + i))
        elif kind == "long":
            blocks.append(paragraph(15, seed + i))
        else:
            blocks.append(" ".join(["token"] * 400))
    assert_invariants("\n\n".join(blocks), size, overlap)
