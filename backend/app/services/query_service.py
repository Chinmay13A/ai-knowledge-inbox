"""Question answering: retrieve relevant chunks, ask the LLM to answer from them, keep the citations."""

import logging
import sqlite3
import time

from app.ai.embeddings.base import Embedder
from app.ai.llm.base import ChatModel
from app.models.answer import Answer
from app.services import retriever
from app.services.prompting import NO_SOURCES_ANSWER, build_messages, extract_citations

logger = logging.getLogger(__name__)


async def answer_question(
    conn: sqlite3.Connection,
    embedder: Embedder,
    chat_model: ChatModel,
    question: str,
    *,
    top_k: int,
    min_score: float,
) -> Answer:
    # Fail fast on missing configuration, before any provider quota is spent.
    embedder.check_ready()
    chat_model.check_ready()

    start = time.perf_counter()
    chunks = await retriever.retrieve(conn, embedder, question, top_k=top_k, min_score=min_score)
    retrieval_ms = _ms_since(start)

    if not chunks:
        # Nothing relevant: answering anyway could only produce a hallucination, so skip the LLM.
        _log_answered(question, retrieved=0, retrieval_ms=retrieval_ms)
        return Answer(text=NO_SOURCES_ANSWER, sources=[])

    system, user = build_messages(question, chunks)
    llm_start = time.perf_counter()
    completion = await chat_model.generate(system=system, user=user)
    llm_ms = _ms_since(llm_start)

    cited, invalid = extract_citations(completion.text, len(chunks))
    _log_answered(
        question,
        retrieved=len(chunks),
        retrieval_ms=retrieval_ms,
        cited=len(cited),
        invalid_citations=invalid,
        top_score=round(chunks[0].score, 4),
        llm_model=chat_model.model_id,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        truncated=completion.truncated,
        llm_ms=llm_ms,
    )
    return Answer(
        text=completion.text,
        sources=chunks,
        cited=cited,
        model_id=chat_model.model_id,
        truncated=completion.truncated,
    )


def _log_answered(question: str, **fields: object) -> None:
    logger.info("query.answered", extra={"question_chars": len(question), **fields})  # never the question text


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
