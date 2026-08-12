"""
SQLAlchemy database setup — SQLite, stored at ./projects/bindcraft.db
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings

DATABASE_URL = f"sqlite:///{settings.projects_dir}/bindcraft.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables."""
    from backend import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
