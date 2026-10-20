import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.ai.llm.base import UnconfiguredChatModel
from app.errors import EmbeddingError, LLMError
from app.services.prompting import NO_SOURCES_ANSWER
from tests.conftest import FakeChatModel, FakeEmbedder, add_note

RAG_NOTE = "Retrieval augmented generation retrieves relevant chunks and passes them to the language model."


def ask(client: TestClient, question: str, **extra: object):  # noqa: ANN201
    return client.post("/query", json={"question": question, **extra})


@pytest.fixture
def inbox(client: TestClient, app: FastAPI) -> dict[str, int]:
    app.state.settings.retrieval_min_score = 0.2  # FakeEmbedder scores are bag-of-words overlaps
    return {
        "rag": add_note(client, RAG_NOTE)["id"],
        "groceries": add_note(client, "Buy milk, eggs and bread.")["id"],
    }


def test_answers_with_numbered_cited_sources(client: TestClient, inbox: dict, chat_model: FakeChatModel) -> None:
    chat_model.answer = "RAG passes retrieved chunks to the model [1]."

    response = ask(client, "  How does retrieval augmented generation work?  ")

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "How does retrieval augmented generation work?"
    assert body["answer"] == "RAG passes retrieved chunks to the model [1]."
    assert body["model"] == "fake:chat"
    assert body["truncated"] is False
    first = body["sources"][0]
    assert first["id"] == 1 and first["cited"] is True
    assert first["item_id"] == inbox["rag"]
    assert first["snippet"] == RAG_NOTE
    assert set(first) == {
        "id",
        "cited",
        "item_id",
        "item_title",
        "item_url",
        "source_type",
        "chunk_index",
        "snippet",
        "score",
    }
    assert [s["id"] for s in body["sources"]] == list(range(1, len(body["sources"]) + 1))


def test_prompt_contains_context_and_question(client: TestClient, inbox: dict, chat_model: FakeChatModel) -> None:
    ask(client, "How does retrieval augmented generation work?")

    system, user = chat_model.prompts[-1]
    assert "untrusted data" in system
    assert RAG_NOTE in user
    assert user.endswith("Question: How does retrieval augmented generation work?")


def test_uncited_sources_are_flagged(client: TestClient, inbox: dict, app: FastAPI, chat_model: FakeChatModel) -> None:
    app.state.settings.retrieval_min_score = -1.0  # retrieve both notes
    chat_model.answer = "Only the second source matters [2]."

    sources = ask(client, "retrieval milk").json()["sources"]

    assert [(s["id"], s["cited"]) for s in sources] == [(1, False), (2, True)]


def test_hallucinated_citation_numbers_are_ignored(client: TestClient, inbox: dict, chat_model: FakeChatModel) -> None:
    chat_model.answer = "Something [7]."

    sources = ask(client, "retrieval augmented generation").json()["sources"]

    assert sources and not any(s["cited"] for s in sources)


def test_nothing_relevant_skips_the_llm(client: TestClient, chat_model: FakeChatModel) -> None:
    response = ask(client, "What is the capital of Peru?")

    assert response.status_code == 200
    assert response.json() == {
        "question": "What is the capital of Peru?",
        "answer": NO_SOURCES_ANSWER,
        "sources": [],
        "model": None,
        "truncated": False,
    }
    assert chat_model.prompts == []


def test_irrelevant_question_with_content_skips_the_llm(
    client: TestClient, inbox: dict, chat_model: FakeChatModel
) -> None:
    body = ask(client, "capital of Peru").json()

    assert body["answer"] == NO_SOURCES_ANSWER
    assert chat_model.prompts == []


def test_truncated_flag_is_passed_through(client: TestClient, inbox: dict, chat_model: FakeChatModel) -> None:
    chat_model.truncated = True

    assert ask(client, "retrieval augmented generation").json()["truncated"] is True


def test_llm_failure_is_502(client: TestClient, inbox: dict, chat_model: FakeChatModel) -> None:
    chat_model.error = LLMError("Gemini rate limit reached, try again shortly")

    response = ask(client, "retrieval augmented generation")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_failed"
    assert response.json()["error"]["message"] == "Gemini rate limit reached, try again shortly"


def test_embedding_failure_is_502(client: TestClient, inbox: dict, embedder: FakeEmbedder) -> None:
    embedder.error = EmbeddingError("Could not reach Gemini")

    response = ask(client, "retrieval")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "embedding_failed"


@pytest.mark.parametrize("missing", ["embedder", "chat_model"])
def test_missing_configuration_is_503_before_any_provider_call(
    app: FastAPI, embedder: FakeEmbedder, chat_model: FakeChatModel, missing: str
) -> None:
    if missing == "embedder":
        app.state.embedder = UnconfiguredEmbedder()
    else:
        app.state.chat_model = UnconfiguredChatModel()

    with TestClient(app) as client:
        response = ask(client, "anything")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_not_configured"
    assert embedder.query_calls == [] and chat_model.prompts == []


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "  "},
        {"question": "x" * 1_001},
        {"question": "ok", "top_k": 0},
        {"question": "ok", "top_k": 21},
        {},
    ],
)
def test_invalid_requests(client: TestClient, payload: dict) -> None:
    response = client.post("/query", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
