from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.course import Course  # Preserve existing imports and register the table.
from app.models.schedule import Schedule  # Register the independent timetable.
from app.models.study_plan import StudyPlan  # Preserve existing imports and table data.
from app.models.kb_document import KBDocument  # Register administrator document storage.


class Document(Base):
    __tablename__ = "documents"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    chunk_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(String(255), default="")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100), default="新对话")
    # Atomic lease: prevents overlapping agent runs across API workers.
    run_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    run_started_at: Mapped[int] = mapped_column(default=0)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    events: Mapped[list] = mapped_column(JSON, default=list)
