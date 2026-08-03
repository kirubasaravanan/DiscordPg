"""RAG knowledge base ingestion and retrieval (docs/AI_DESIGN.md §3). All
pgvector interaction lives here — ai_engine/ never queries the database
itself; it only embeds/answers whatever text it's given (docs/AI_DESIGN.md §1).

Run ingestion from backend/: `uv run python -m app.services.rag_service`
(same invocation style as app/database/seed.py). Re-run any time a file
under app/content/ changes — there's no separate admin endpoint for this
in v1, matching how seeding is also script-only, not API-triggered.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import RagDocumentChunk
from app.services import ai_client

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
TOP_K = 4


def _chunk_markdown(text: str) -> list[str]:
    """Splits on `##` headings — one chunk per section. See
    docs/AI_DESIGN.md §3 for why: these files are short and already
    organized into coherent sections, so heading boundaries keep each
    chunk topically self-contained better than a fixed token window would
    at this content size.
    """
    sections = text.split("\n## ")
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        if i > 0:
            section = "## " + section  # restore the marker split() consumed
        chunks.append(section)
    return chunks


def ingest_documents(db: Session) -> int:
    """Re-embeds every `*.md` file under app/content/ and replaces that
    file's chunks in the database. Idempotent — safe to re-run any time a
    content file changes (e.g. after an owner edits pg_rules.md); deletes
    and regenerates per-source rather than diffing, since these files are
    small and fully regenerable. Returns the total chunk count stored.
    """
    total = 0
    for path in sorted(CONTENT_DIR.glob("*.md")):
        source = path.name
        chunks = _chunk_markdown(path.read_text(encoding="utf-8"))

        db.query(RagDocumentChunk).filter(RagDocumentChunk.source == source).delete()

        for index, content in enumerate(chunks):
            embedding = ai_client.embed_text(content)
            db.add(RagDocumentChunk(source=source, chunk_index=index, content=content, embedding=embedding))
        total += len(chunks)
        logger.info("Ingested %d chunks from %s", len(chunks), source)

    db.commit()
    return total


def answer_faq(db: Session, question: str) -> dict:
    """Embeds the question, retrieves the TOP_K nearest chunks by cosine
    distance, and asks ai_engine/ to answer using only that context.

    `cited_sources` is built from the retrieved chunks directly, not
    parsed out of the model's generated text — true by construction, not
    dependent on the model accurately citing itself. See docs/AI_DESIGN.md §3.
    """
    query_embedding = ai_client.embed_text(question)

    nearest = (
        db.query(RagDocumentChunk)
        .order_by(RagDocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(TOP_K)
        .all()
    )

    if not nearest:
        return {
            "answer": "I don't have any information to answer that yet — the knowledge base hasn't been set up.",
            "cited_sources": [],
        }

    context = [{"source": chunk.source, "content": chunk.content} for chunk in nearest]
    answer = ai_client.answer_question(question, context)
    cited_sources = sorted({chunk.source for chunk in nearest})
    return {"answer": answer, "cited_sources": cited_sources}


if __name__ == "__main__":
    from app.database.connection import SessionLocal

    session = SessionLocal()
    try:
        count = ingest_documents(session)
        print(f"Ingested {count} chunks total from {CONTENT_DIR}.")
    finally:
        session.close()
