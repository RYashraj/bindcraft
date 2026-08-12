"""
SQLAlchemy ORM models for BindCraft.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Uploaded file paths (relative to projects/<id>/input/)
    pdb_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ligand_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ligand_name: Mapped[str | None] = mapped_column(String(10), nullable=True)  # residue name
    ligand_charge: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Project state: new / configured / ready / completed
    status: Mapped[str] = mapped_column(String(20), default="new")

    # JSON blob of wizard settings
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="project", cascade="all, delete-orphan"
    )

    def is_demo(self) -> bool:
        return self.id == "demo-acetylcholinesterase"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Mode: generate | run
    mode: Mapped[str] = mapped_column(String(20), default="generate")

    # Status: queued | running | success | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued")

    # Current step label (for progress display)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Error message in plain English
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationship
    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
