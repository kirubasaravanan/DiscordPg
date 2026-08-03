from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin

# Must match ai_engine/config.py's OLLAMA_EMBED_MODEL output size
# (nomic-embed-text = 768 dimensions). Not verified against a live model in
# this environment — see docs/AI_DESIGN.md §3 and docs/ARCHITECTURE.md §12
# item 27. Changing the embedding model requires a new migration to alter
# this dimension before re-ingesting.
EMBEDDING_DIMENSIONS = 768


class RagDocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """RAG knowledge base for the tenant FAQ (docs/AI_DESIGN.md §3).

    Not soft-deleted, unlike most of this schema — `rag_service.py`'s
    ingestion deletes and regenerates all rows for a given `source` on
    each run. The source files (backend/app/content/*.md) are small and
    fully regenerable, unlike tenant data, so there's no history worth
    keeping around a stale chunk the way there is for e.g. a complaint.
    """

    __tablename__ = "rag_document_chunks"
    __table_args__ = (Index("ix_rag_document_chunks_source", "source"),)

    source: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
