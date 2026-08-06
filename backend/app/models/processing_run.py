from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        CheckConstraint(
            "execution_status IN "
            "('pending', 'running', 'succeeded', 'failed')",
            name="ck_processing_runs_execution_status",
        ),
        CheckConstraint(
            "verification_status IN "
            "('not_run', 'pending', 'pass', 'warning', 'fail')",
            name="ck_processing_runs_verification_status",
        ),
        CheckConstraint(
            "parser_warning_count >= 0 "
            "AND normalizer_warning_count >= 0 "
            "AND verification_error_count >= 0 "
            "AND verification_warning_count >= 0",
            name="ck_processing_runs_counts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "documents.id",
            name="fk_processing_runs_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    execution_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_run",
        server_default="not_run",
        index=True,
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    pipeline_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    output_root_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_stage: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    parser_warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    normalizer_warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    verification_error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    verification_warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped["Document"] = relationship(
        back_populates="processing_runs",
    )
    artifacts: Mapped[list["ProcessingArtifact"]] = relationship(
        back_populates="processing_run",
        cascade="all, delete-orphan",
    )