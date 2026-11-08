from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.services import kb_document_service as service

router = APIRouter(prefix="/admin/kb-documents", tags=["课程资料管理（管理员）"],
                   dependencies=[Depends(get_current_admin)])


@router.get("")
def list_documents(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                   keywords: str = Query("", max_length=100), db: Session = Depends(get_db)):
    return Response.success(data=service.list_documents(db, page, page_size, keywords))


@router.post("/batch", summary="批量上传资料（整批提交或回滚）")
def upload_batch(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    try:
        return Response.success(data=service.upload_batch(db, files))
    finally:
        for file in files:
            file.file.close()


@router.get("/{document_id}/preview")
def preview(document_id: int, db: Session = Depends(get_db)):
    return Response.success(data=service.preview_document(db, document_id))


@router.delete("/{document_id}")
def delete(document_id: int, db: Session = Depends(get_db)):
    return Response.success(data=service.delete_document(db, document_id))
