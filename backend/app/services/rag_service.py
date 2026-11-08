"""Private document ingestion and retrieval; no original file is publicly mounted."""
import hashlib
import logging
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.campus import Document
from app.services.campus_service import owned
from app.services.course_service import get_visible_course

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
MAX_TEXT_LENGTH = 60000  # Fits MySQL TEXT even for four-byte Unicode.
ALLOWED_DOCUMENT_TYPES = {".pdf", ".docx", ".txt", ".md"}
logger = logging.getLogger(__name__)


def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(422, "仅支持 PDF、DOCX、TXT、Markdown 文档")
    if not content or len(content) > MAX_DOCUMENT_SIZE:
        raise HTTPException(413, "文档不能为空且不能超过 10MB")
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ValueError("PDF 不能加密且不能超过 100 页")
            pages = [page.extract_text() or "" for page in reader.pages]
            if not any(page.strip() for page in pages):
                raise ValueError("扫描 PDF 暂不支持，请先 OCR 转为可复制文本")
            text = "\n\n".join(f"[第 {number} 页]\n{page}" for number, page in enumerate(pages, 1))
        elif ext == ".docx":
            from docx import Document as DocxDocument

            with ZipFile(BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValueError("DOCX 解压后过大")
            document = DocxDocument(BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            paragraphs.extend(" | ".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows)
            text = "\n\n".join(paragraphs)
        else:
            text = content.decode("utf-8-sig")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "文档解析失败，请使用未加密、含文本的 PDF/DOCX 或 UTF-8 文本") from exc
    text = text.replace("\x00", "").strip()
    if not text:
        raise HTTPException(422, "未提取到有效文本")
    if len(text.encode("utf-8")) > MAX_TEXT_LENGTH:
        raise HTTPException(422, "提取的文本超过 60KB，请拆分文档后上传")
    return text


def split_text(text: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=120,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    ).split_text(text)


def embedding_client():
    from langchain_openai import OpenAIEmbeddings

    if not settings.EMBEDDING_API_KEY:
        raise HTTPException(503, "请配置 EMBEDDING_API_KEY 后再使用资料索引和检索")
    return OpenAIEmbeddings(
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_BASE_URL,
        model=settings.EMBEDDING_MODEL,
        check_embedding_ctx_length=False, timeout=30, max_retries=1,
    )


@lru_cache(maxsize=1)
def collection():
    import chromadb
    from chromadb.config import Settings

    # An embedding-model change creates a separate index, preventing mixed dimensions.
    namespace = hashlib.sha256(
        f"{settings.EMBEDDING_BASE_URL}|{settings.EMBEDDING_MODEL}".encode()
    ).hexdigest()[:12]
    client = chromadb.HttpClient(
        host=settings.CHROMA_HOST, port=settings.CHROMA_PORT,
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        f"campus-{namespace}", embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )


def document_info(row: Document):
    return {"id": row.id, "name": row.name, "course_id": row.course_id,
            "status": row.status, "chunk_count": row.chunk_count,
            "error": row.error, "create_time": row.create_time.isoformat()}


def index_document(db: Session, row: Document):
    """Use deterministic chunk IDs so a failed ingestion can safely be retried."""
    row.status, row.error = "pending", ""
    db.commit()
    try:
        chunks = split_text(row.content)
        embedder = embedding_client()
        store = collection()
        store.delete(where={"document_id": row.id})
        for offset in range(0, len(chunks), 16):
            batch = chunks[offset:offset + 16]
            vectors = embedder.embed_documents(batch)
            store.upsert(
                ids=[f"{row.id}:{offset + index}" for index in range(len(batch))],
                documents=batch, embeddings=vectors,
                metadatas=[{"user_id": row.user_id, "document_id": row.id,
                            "chunk": offset + index + 1}
                           for index in range(len(batch))],
            )
        row.status, row.chunk_count = "ready", len(chunks)
    except Exception:
        logger.exception("Document indexing failed: document_id=%s", row.id)
        # Retrieval also checks SQL status, so a partially written index is never used.
        row.status, row.error = "failed", "索引失败，请检查 Embedding 配置和 Chroma 服务后重试"
    db.commit()
    db.refresh(row)
    return document_info(row)


def create_document(db: Session, user_id: int, filename: str, content: bytes, course_id: int | None):
    if course_id is not None:
        get_visible_course(db, user_id, course_id)
    text = extract_text(filename, content)
    row = Document(user_id=user_id, course_id=course_id, name=filename[:255], content=text)
    db.add(row)
    db.commit()
    db.refresh(row)
    return index_document(db, row)


def search_documents(db: Session, user_id: int, query: str, course_id: int | None = None, limit: int = 5):
    if not query.strip() or len(query) > 2000 or not 1 <= limit <= 8:
        raise HTTPException(422, "检索参数不合法")
    statement = select(Document).where(Document.user_id == user_id, Document.status == "ready")
    if course_id is not None:
        get_visible_course(db, user_id, course_id)
        statement = statement.where(Document.course_id == course_id)
    documents = {row.id: row for row in db.scalars(statement).all()}
    if not documents:
        return []
    try:
        vector = embedding_client().embed_query(query)
        result = collection().query(
            query_embeddings=[vector], n_results=limit,
            where={"$and": [{"user_id": user_id}, {"document_id": {"$in": list(documents)}}]},
            include=["documents", "metadatas", "distances"],
        )
        sources = []
        for text, metadata in zip(result["documents"][0], result["metadatas"][0]):
            # Defense in depth: vector metadata never decides authorization.
            doc = documents.get(metadata.get("document_id"))
            if doc is not None and metadata.get("user_id") == user_id:
                chunk = metadata["chunk"]
                sources.append({"document_id": doc.id, "name": doc.name, "chunk": chunk,
                                "citation": f"资料{doc.id}-片段{chunk}", "text": text})
        return sources
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "资料检索暂不可用，请检查 Embedding 和 Chroma 服务") from exc


def delete_document(db: Session, user_id: int, document_id: int):
    row = owned(db, Document, document_id, user_id)
    try:
        collection().delete(where={"document_id": row.id})
    except Exception as exc:
        raise HTTPException(503, "Chroma 暂不可用，资料尚未删除，请稍后重试") from exc
    db.delete(row)
    db.commit()
