from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KBDocument(Base):
    __tablename__ = "kb_documents"

    file_name: Mapped[str] = mapped_column(String(255))
    # Relative private storage key, never a public URL or caller-supplied path.
    file_path: Mapped[str] = mapped_column(String(255), unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger)
    file_type: Mapped[str] = mapped_column(String(16))
    text_content: Mapped[str] = mapped_column(Text)
