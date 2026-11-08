from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.response import PageResponse
from app.models.campus import Document
from app.models.course import Course
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.course import AdminCourseRequest, AdminCourseResponse, CourseResponse


def visible_courses_query(user_id: int, on_date: date | None = None):
    scheduled = select(Schedule.course_id).where(Schedule.student_id == user_id)
    if on_date is not None:
        scheduled = scheduled.where(
            Schedule.weekday == on_date.isoweekday(),
            Schedule.start_date <= on_date, Schedule.end_date >= on_date,
        )
        return select(Course).where(Course.id.in_(scheduled))
    return select(Course).where(or_(Course.user_id == user_id, Course.id.in_(scheduled)))


def get_visible_course(db: Session, user_id: int, course_id: int):
    row = db.scalar(visible_courses_query(user_id).where(Course.id == course_id))
    if row is None:
        raise HTTPException(404, "课程不存在")
    return row


def _response(course: Course, user: User) -> AdminCourseResponse:
    return AdminCourseResponse(
        **CourseResponse.model_validate(course).model_dump(),
        user_id=course.user_id, username=user.username, user_name=user.name,
        create_time=course.create_time, update_time=course.update_time,
    )


def _get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "课程不存在")
    return course


def get_course_list(
    db: Session, page: int = 1, page_size: int = 10,
    keywords: str | None = None, user_id: int | None = None,
) -> PageResponse:
    query = select(Course, User).join(User, Course.user_id == User.id)
    if keywords and keywords.strip():
        pattern = f"%{keywords.strip()}%"
        query = query.where(or_(Course.name.ilike(pattern), Course.teacher.ilike(pattern)))
    if user_id is not None:
        query = query.where(Course.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Course.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return PageResponse(list=[_response(course, user) for course, user in rows], total=total)


def get_course_detail(db: Session, course_id: int) -> AdminCourseResponse:
    course = _get_course(db, course_id)
    return _response(course, db.get(User, course.user_id))


def create_course(db: Session, data: AdminCourseRequest) -> AdminCourseResponse:
    user = db.get(User, data.user_id)
    if user is None:
        raise HTTPException(404, "所属用户不存在")
    course = Course(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return _response(course, user)


def update_course(db: Session, course_id: int, data: AdminCourseRequest) -> AdminCourseResponse:
    course = _get_course(db, course_id)
    user = db.get(User, data.user_id)
    if user is None:
        raise HTTPException(404, "所属用户不存在")
    if course.user_id != data.user_id and db.scalar(
        select(Document.id).where(Document.course_id == course_id).limit(1)
    ):
        raise HTTPException(409, "课程已关联私有资料，不能更换所属用户")
    for field, value in data.model_dump().items():
        setattr(course, field, value)
    db.commit()
    db.refresh(course)
    return _response(course, user)


def delete_course(db: Session, course_id: int):
    course = _get_course(db, course_id)
    if db.scalar(select(Schedule.id).where(Schedule.course_id == course_id).limit(1)):
        raise HTTPException(409, "该课程已排课，请先删除关联课表")
    if db.scalar(select(Document.id).where(Document.course_id == course_id).limit(1)):
        raise HTTPException(409, "请先删除该课程关联的资料")
    db.delete(course)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "课程已关联课表或资料，请刷新后重试") from exc
