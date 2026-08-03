"""rag_service.py's chunking/ingestion/retrieval/citation logic, against
real Postgres + pgvector. ai_client's embed/answer calls are substituted
with controlled, deterministic values — ai_client's own HTTP contract with
ai_engine is already verified for real in test_ai_client.py; what these
tests need is precise control over "what the embeddings are" to assert
correct nearest-neighbor retrieval, which a live (even fake-Ollama-backed)
embedding call can't give deterministically per-input.
"""

from app.models.rag_document_chunk import EMBEDDING_DIMENSIONS, RagDocumentChunk
from app.services import rag_service


def _vector(hot_index: int) -> list[float]:
    """A one-hot-ish vector so cosine distance between two of these is
    unambiguous — exact match at `hot_index`, orthogonal otherwise.
    """
    v = [0.0] * EMBEDDING_DIMENSIONS
    v[hot_index] = 1.0
    return v


def test_chunk_markdown_splits_on_headings():
    text = "# Title\n\nintro text\n\n## Section A\ncontent a\n\n## Section B\ncontent b\n"

    chunks = rag_service._chunk_markdown(text)

    assert len(chunks) == 3
    assert chunks[0].startswith("# Title")
    assert "intro text" in chunks[0]
    assert chunks[1] == "## Section A\ncontent a"
    assert chunks[2] == "## Section B\ncontent b"


def test_ingest_documents_stores_real_content_files(db_session, monkeypatch):
    monkeypatch.setattr(rag_service.ai_client, "embed_text", lambda text: _vector(0))

    total = rag_service.ingest_documents(db_session)

    stored = db_session.query(RagDocumentChunk).all()
    assert len(stored) == total
    assert total > 0
    sources = {chunk.source for chunk in stored}
    assert sources == {"pg_rules.md", "rent_policy.md", "maintenance_instructions.md"}
    # chunk_index is contiguous per source, starting at 0
    for source in sources:
        indices = sorted(c.chunk_index for c in stored if c.source == source)
        assert indices == list(range(len(indices)))


def test_ingest_documents_replaces_rather_than_duplicates(db_session, monkeypatch):
    monkeypatch.setattr(rag_service.ai_client, "embed_text", lambda text: _vector(0))

    first_total = rag_service.ingest_documents(db_session)
    second_total = rag_service.ingest_documents(db_session)

    assert first_total == second_total
    assert db_session.query(RagDocumentChunk).count() == second_total


def test_answer_faq_retrieves_nearest_chunk_and_cites_its_source(db_session, monkeypatch):
    # TOP_K is 4, so 5 chunks means the query must actually rank by
    # distance rather than just returning everything it has.
    near = RagDocumentChunk(source="rent_policy.md", chunk_index=0, content="Rent is due on the 5th.", embedding=_vector(0))
    fillers = [
        RagDocumentChunk(source="pg_rules.md", chunk_index=i, content=f"filler {i}", embedding=_vector(100 + i))
        for i in range(4)
    ]
    db_session.add_all([near, *fillers])
    db_session.flush()

    monkeypatch.setattr(rag_service.ai_client, "embed_text", lambda text: _vector(0))
    captured_context = {}

    def fake_answer_question(question, context):
        captured_context["question"] = question
        captured_context["context"] = context
        return "Rent is due on the 5th of each month."

    monkeypatch.setattr(rag_service.ai_client, "answer_question", fake_answer_question)

    result = rag_service.answer_faq(db_session, "When is rent due?")

    assert result["answer"] == "Rent is due on the 5th of each month."
    assert "rent_policy.md" in result["cited_sources"]
    # the exact-match chunk is the closest possible (distance 0) to every
    # other vector here, so it must be first in the retrieved context
    assert captured_context["context"][0] == {"source": "rent_policy.md", "content": "Rent is due on the 5th."}
    assert len(captured_context["context"]) == rag_service.TOP_K


def test_answer_faq_with_empty_knowledge_base_skips_the_model_call(db_session, monkeypatch):
    monkeypatch.setattr(rag_service.ai_client, "embed_text", lambda text: _vector(0))
    called = []
    monkeypatch.setattr(rag_service.ai_client, "answer_question", lambda *a, **k: called.append(1))

    result = rag_service.answer_faq(db_session, "anything")

    assert result["cited_sources"] == []
    assert "don't have any information" in result["answer"]
    assert called == []
