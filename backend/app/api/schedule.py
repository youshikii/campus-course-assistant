from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.schedule import ScheduleRequest
from app.services import schedule_service

router = APIRouter(tags=["课表"])
admin_router = APIRouter(
    prefix="/admin/schedules", tags=["课表管理（管理员）"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/schedules/me")
def my_schedules(
    on_date: date | None = None,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    # Identity comes only from JWT, never a caller-supplied student_id.
    return Response.success(data=schedule_service.get_my_schedules(db, user.id, on_date))


@admin_router.get("")
def list_schedules(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    student_id: int | None = Query(None, gt=0), on_date: date | None = None,
    course_id: int | None = Query(None, gt=0), db: Session = Depends(get_db),
):
    return Response.success(data=schedule_service.get_schedule_list(db, page, page_size, student_id, on_date, course_id))


@admin_router.get("/student-options")
def student_options(keywords: str = Query("", max_length=100), db: Session = Depends(get_db)):
    return Response.success(data=schedule_service.get_student_options(db, keywords))


@admin_router.get("/{schedule_id}")
def detail(schedule_id: int, db: Session = Depends(get_db)):
    return Response.success(data=schedule_service.get_schedule_detail(db, schedule_id))


@admin_router.post("")
def create(data: ScheduleRequest, db: Session = Depends(get_db)):
    return Response.success(data=schedule_service.create_schedule(db, data))


@admin_router.put("/{schedule_id}")
def update(schedule_id: int, data: ScheduleRequest, db: Session = Depends(get_db)):
    return Response.success(data=schedule_service.update_schedule(db, schedule_id, data))


@admin_router.delete("/{schedule_id}")
def delete(schedule_id: int, db: Session = Depends(get_db)):
    schedule_service.delete_schedule(db, schedule_id)
    return Response.success()
