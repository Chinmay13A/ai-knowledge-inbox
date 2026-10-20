from pathlib import Path

from app.db import connect, init_db
from app.models.chunk import ChunkingConfig
from app.repositories import chunks_repo, items_repo
from app.services.ingest_service import backfill_chunks


def test_backfill_chunks_items_saved_before_chunking(tmp_path: Path) -> None:
    db_path = str(tmp_path / "old.db")
    init_db(db_path)
    conn = connect(db_path)
    with conn:  # simulate items saved by an older version, without chunks
        old_note = items_repo.create_item(conn, source_type="note", title="Old", content="An old note.")
        old_page = items_repo.create_item(conn, source_type="url", title="Page", content="Sentence. " * 300)

    items, chunks = backfill_chunks(conn, ChunkingConfig(size=800, overlap=100))

    assert items == 2
    assert chunks == len(chunks_repo.list_chunks(conn, old_note.id)) + len(chunks_repo.list_chunks(conn, old_page.id))
    assert len(chunks_repo.list_chunks(conn, old_page.id)) > 1
    assert backfill_chunks(conn, ChunkingConfig()) == (0, 0)  # idempotent
    conn.close()
