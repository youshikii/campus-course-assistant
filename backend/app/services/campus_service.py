from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.campus import Course
from app.schemas.campus import CourseRequest, CourseResponse
from app.schemas.course import AdminCourseRequest
from app.services import course_service
from app.services.study_plan_service import save_plan, list_plans  # Compatible imports.


def owned(db: Session, model, row_id: int, user_id: int):
    row = db.scalar(select(model).where(model.id == row_id, model.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


def list_courses(db: Session, user_id: int, on_date: date | None = None):
    query = course_service.visible_courses_query(user_id, on_date)
    courses = db.scalars(query.order_by(Course.weekday, Course.start_time, Course.id)).all()
    return [CourseResponse.model_validate(row).model_dump(mode="json") for row in courses]


def save_course(db: Session, user_id: int, data: CourseRequest, course_id: int | None = None):
    payload = AdminCourseRequest(user_id=user_id, **data.model_dump())
    if course_id:
        owned(db, Course, course_id, user_id)
        result = course_service.update_course(db, course_id, payload)
    else:
        result = course_service.create_course(db, payload)
    return CourseResponse(**result.model_dump())


def delete_course(db: Session, user_id: int, course_id: int):
    owned(db, Course, course_id, user_id)
    course_service.delete_course(db, course_id)
