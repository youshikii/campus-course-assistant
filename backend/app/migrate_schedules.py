"""Explicit one-time upgrade of legacy per-course weekly slots. Never runs on startup."""
from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleRequest


def migrate_legacy_schedules(db: Session):
    courses = db.scalars(select(Course).join(User, Course.user_id == User.id).where(
        User.role == "student",
        ~exists().where(Schedule.course_id == Course.id, Schedule.student_id == Course.user_id),
    )).all()
    migrated, invalid = 0, []
    for course in courses:
        try:
            data = ScheduleRequest(
                student_id=course.user_id, course_id=course.id, weekday=course.weekday,
                start_time=course.start_time, end_time=course.end_time,
                start_date=course.start_date, end_date=course.end_date,
                location=course.location, notes=course.notes,
            )
        except ValidationError:
            invalid.append(course.id)
            continue
        db.add(Schedule(**data.model_dump()))
        migrated += 1
    db.commit()
    return {"migrated": migrated, "invalid_course_ids": invalid}
