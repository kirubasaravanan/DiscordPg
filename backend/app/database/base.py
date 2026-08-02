import datetime
import decimal
import uuid

from sqlalchemy import DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every model. Registers the project-wide
    column type conventions from docs/DATABASE.md so individual models
    don't have to repeat them (e.g. `Mapped[decimal.Decimal]` always
    becomes `NUMERIC(10, 2)`).
    """

    type_annotation_map = {
        datetime.datetime: DateTime(timezone=True),
        decimal.Decimal: Numeric(10, 2),
        uuid.UUID: UUID(as_uuid=True),
    }
