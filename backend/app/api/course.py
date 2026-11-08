from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.schemas.course import AdminCourseRequest
from app.services import course_service

router = APIRouter(
    prefix="/admin/courses", tags=["课程管理（管理员）"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("")
def list_courses(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    keywords: str | None = Query(None, max_length=100),
    user_id: int | None = Query(None, gt=0), db: Session = Depends(get_db),
):
    return Response.success(data=course_service.get_course_list(db, page, page_size, keywords, user_id))


@router.get("/{course_id}")
def course_detail(course_id: int, db: Session = Depends(get_db)):
    return Response.success(data=course_service.get_course_detail(db, course_id))


@router.post("")
def create_course(data: AdminCourseRequest, db: Session = Depends(get_db)):
    return Response.success(data=course_service.create_course(db, data))


@router.put("/{course_id}")
def update_course(course_id: int, data: AdminCourseRequest, db: Session = Depends(get_db)):
    return Response.success(data=course_service.update_course(db, course_id, data))


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    course_service.delete_course(db, course_id)
    return Response.success()
