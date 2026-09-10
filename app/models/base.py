"""SQLAlchemy base: UUID hex PKs, timestamps, naming convention."""
import datetime

from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class UUIDPk:
    id: Mapped[str] = mapped_column(String(32), primary_key=True)


class Timestamped:
    created_at: Mapped[datetime.datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=utcnow, onupdate=utcnow)
