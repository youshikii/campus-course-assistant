from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.campus import CourseRequest
from app.services import campus_service as service

router = APIRouter(tags=["个人课程（兼容接口）"])


@router.get("/courses")
def courses(on_date: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=service.list_courses(db, user.id, on_date))


@router.post("/courses")
def create_course(data: CourseRequest, user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return Response.success(data=service.save_course(db, user.id, data))


@router.put("/courses/{course_id}")
def update_course(course_id: int, data: CourseRequest, user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return Response.success(data=service.save_course(db, user.id, data, course_id))


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    service.delete_course(db, user.id, course_id)
    return Response.success()
