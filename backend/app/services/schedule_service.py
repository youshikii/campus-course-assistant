from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.response import PageResponse
from app.models.course import Course
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import AdminScheduleResponse, ScheduleRequest, ScheduleResponse


def get_student_options(db: Session, keywords: str = ""):
    query = select(User).where(User.role == "student")
    if keywords.strip():
        pattern = f"%{keywords.strip()}%"
        query = query.where(or_(User.username.ilike(pattern), User.name.ilike(pattern)))
    users = db.scalars(query.order_by(User.id.desc()).limit(30)).all()
    return [{"id": user.id, "username": user.username, "name": user.name,
             "status": user.status} for user in users]


def _on_date(query, on_date: date | None):
    if on_date is not None:
        query = query.where(
            Schedule.weekday == on_date.isoweekday(),
            Schedule.start_date <= on_date,
            Schedule.end_date >= on_date,
        )
    return query


def _public_response(schedule: Schedule, course: Course) -> ScheduleResponse:
    return ScheduleResponse(
        id=schedule.id, course_id=schedule.course_id, name=course.name,
        teacher=course.teacher, weekday=schedule.weekday,
        start_time=schedule.start_time, end_time=schedule.end_time,
        start_date=schedule.start_date, end_date=schedule.end_date,
        location=schedule.location, notes=schedule.notes,
    )


def _admin_response(schedule: Schedule, course: Course, student: User):
    return AdminScheduleResponse(
        **_public_response(schedule, course).model_dump(),
        student_id=student.id, username=student.username, student_name=student.name,
        create_time=schedule.create_time, update_time=schedule.update_time,
    )


def get_my_schedules(db: Session, student_id: int, on_date: date | None = None):
    query = select(Schedule, Course).join(Course, Schedule.course_id == Course.id)
    query = _on_date(query.where(Schedule.student_id == student_id), on_date)
    rows = db.execute(query.order_by(Schedule.weekday, Schedule.start_time, Schedule.id)).all()
    return [_public_response(schedule, course) for schedule, course in rows]


def schedule_to_dict(schedule: ScheduleResponse) -> dict:
    """Return public fields with JSON-safe ISO dates/times for MCP and models."""
    return ScheduleResponse.model_validate(schedule.model_dump()).model_dump(mode="json")


def get_schedule_list(
    db: Session, page: int = 1, page_size: int = 10,
    student_id: int | None = None, on_date: date | None = None,
    course_id: int | None = None,
):
    query = select(Schedule, Course, User).join(
        Course, Schedule.course_id == Course.id
    ).join(User, Schedule.student_id == User.id)
    if student_id is not None:
        query = query.where(Schedule.student_id == student_id)
    if course_id is not None:
        query = query.where(Schedule.course_id == course_id)
    query = _on_date(query, on_date)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Schedule.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return PageResponse(list=[_admin_response(*row) for row in rows], total=total)


def _get_schedule(db: Session, schedule_id: int):
    row = db.get(Schedule, schedule_id)
    if row is None:
        raise HTTPException(404, "课表记录不存在")
    return row


def get_schedule_detail(db: Session, schedule_id: int):
    row = _get_schedule(db, schedule_id)
    return _admin_response(row, db.get(Course, row.course_id), db.get(User, row.student_id))


def _references(db: Session, data: ScheduleRequest):
    student = db.get(User, data.student_id)
    if student is None:
        raise HTTPException(404, "学生不存在")
    if student.role != "student":
        raise HTTPException(422, "课表只能分配给学生账号")
    course = db.get(Course, data.course_id)
    if course is None:
        raise HTTPException(404, "课程不存在")
    return student, course


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "学生或课程已发生变化，请刷新后重试") from exc


def create_schedule(db: Session, data: ScheduleRequest):
    student, course = _references(db, data)
    row = Schedule(**data.model_dump())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _admin_response(row, course, student)


def update_schedule(db: Session, schedule_id: int, data: ScheduleRequest):
    row = _get_schedule(db, schedule_id)
    student, course = _references(db, data)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    _commit(db)
    db.refresh(row)
    return _admin_response(row, course, student)


def delete_schedule(db: Session, schedule_id: int):
    db.delete(_get_schedule(db, schedule_id))
    _commit(db)
