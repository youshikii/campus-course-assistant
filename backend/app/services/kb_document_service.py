"""Administrator documents: private files, parsed preview, compensated batches."""
import logging
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.common.response import PageResponse
from app.models.kb_document import KBDocument
from app.schemas.kb_document import KBDocumentResponse
from app.services.rag_service import extract_text, MAX_DOCUMENT_SIZE

STORAGE_DIR = BASE_DIR / "data" / "kb_documents"
MAX_BATCH_FILES = 20
MAX_BATCH_SIZE = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


def list_documents(db: Session, page: int, page_size: int, keywords: str = ""):
    query = select(KBDocument)
    if keywords.strip():
        query = query.where(KBDocument.file_name.ilike(f"%{keywords.strip()}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(KBDocument.create_time.desc(), KBDocument.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return PageResponse(list=[KBDocumentResponse.model_validate(row) for row in rows], total=total)


def _write_file(path: Path, content: bytes):
    # Never overwrite an existing file, including on an unlikely UUID collision.
    with path.open("xb") as handle:
        handle.write(content)


def upload_batch(db: Session, files: list[UploadFile]):
    if not 1 <= len(files) <= MAX_BATCH_FILES:
        raise HTTPException(422, "每批需上传 1–20 个文件")
    batch_dir = None
    file_number = 0
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        candidate = STORAGE_DIR / uuid4().hex
        candidate.mkdir()
        batch_dir = candidate  # Cleanup only a directory created by this request.
        rows, total_size = [], 0
        for file_number, file in enumerate(files, 1):
            name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
            if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
                raise HTTPException(422, "文件名不能为空、包含控制字符或超过 255 字符")
            content = file.file.read(MAX_DOCUMENT_SIZE + 1)
            total_size += len(content)
            if total_size > MAX_BATCH_SIZE:
                raise HTTPException(413, "整批文件不能超过 50MB")
            text = extract_text(name, content)
            suffix = Path(name).suffix.lower()
            destination = batch_dir / f"{uuid4().hex}{suffix}"
            _write_file(destination, content)
            row = KBDocument(file_name=name, file_path=destination.relative_to(STORAGE_DIR).as_posix(),
                             file_size=len(content), file_type=suffix[1:], text_content=text)
            db.add(row)
            rows.append(row)
        db.flush()
        # Prepare the response before commit: no fallible DB reads after a successful commit.
        result = [KBDocumentResponse.model_validate(row) for row in rows]
        db.commit()
        return result
    except Exception as exc:
        try:
            db.rollback()
        finally:
            if batch_dir is not None and batch_dir.exists():
                try:
                    shutil.rmtree(batch_dir)
                except OSError:
                    logger.exception("KB batch cleanup failed: %s", batch_dir.name)
                    raise HTTPException(500, "本批记录已回滚，但文件清理失败，请联系管理员") from None
        if isinstance(exc, HTTPException):
            prefix = f"第 {file_number} 个文件：" if file_number else ""
            raise HTTPException(exc.status_code, f"{prefix}{exc.detail}；本批未保存") from None
        raise HTTPException(503, "批量上传失败，本批记录和文件已回滚，请稍后重试") from None


def _get_document(db: Session, document_id: int):
    row = db.get(KBDocument, document_id)
    if row is None:
        raise HTTPException(404, "资料不存在")
    return row


def preview_document(db: Session, document_id: int):
    row = _get_document(db, document_id)
    return {"id": row.id, "file_name": row.file_name, "content": row.text_content}


def _storage_path(key: str):
    root = STORAGE_DIR.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or path == root:
        raise HTTPException(500, "资料存储位置异常，请联系管理员")
    return path


def delete_document(db: Session, document_id: int):
    row = _get_document(db, document_id)
    path = _storage_path(row.file_path)
    trash = None
    if path.exists():
        if not path.is_file():
            raise HTTPException(500, "资料存储位置异常，请联系管理员")
        trash = path.with_name(f".deleted-{uuid4().hex}")
        try:
            path.rename(trash)
        except OSError:
            raise HTTPException(503, "无法删除文件，资料已保留，请稍后重试") from None
    try:
        db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
        if trash is not None:
            try:
                trash.rename(path)
            except OSError:
                logger.exception("KB delete restore failed: document %s", document_id)
                raise HTTPException(500, "删除失败且文件恢复异常，请联系管理员") from None
        raise HTTPException(503, "删除失败，资料已保留，请稍后重试") from None
    cleanup_pending = False
    if trash is not None:
        try:
            trash.unlink()
        except OSError:
            cleanup_pending = True
            logger.warning("KB deleted file awaits cleanup: document %s", document_id)
    try:
        path.parent.rmdir()  # Remove only an empty, now-unused batch directory.
    except OSError:
        pass
    return {"deleted": True, "cleanup_pending": cleanup_pending}
