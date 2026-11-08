from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.campus import Document
from app.models.user import User
from app.schemas.campus import SearchRequest
from app.services.campus_service import owned
from app.services import rag_service as service

router = APIRouter(prefix="/documents", tags=["私有知识库"])


@router.get("")
def documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.id.desc())).all()
    return Response.success(data=[service.document_info(row) for row in rows])


@router.post("")
def upload_document(file: UploadFile = File(...), course_id: int | None = Form(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        content = file.file.read(service.MAX_DOCUMENT_SIZE + 1)
        name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        result = service.create_document(db, user.id, name, content, course_id)
        return Response.success(data=result)
    finally:
        file.file.close()


@router.post("/search")
def search(data: SearchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=service.search_documents(db, user.id, data.query, data.course_id, data.limit))


@router.get("/{document_id}")
def detail(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(db, Document, document_id, user.id)
    return Response.success(data={**service.document_info(row), "content": row.content})


@router.post("/{document_id}/index")
def reindex(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(db, Document, document_id, user.id)
    return Response.success(data=service.index_document(db, row))


@router.delete("/{document_id}")
def delete(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.delete_document(db, user.id, document_id)
    return Response.success()
