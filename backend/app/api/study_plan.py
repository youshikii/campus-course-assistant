from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.study_plan import PlanRequest, PlanStatus, PlanStatusRequest
from app.services import study_plan_service as service

router = APIRouter(tags=["个人学习计划"])


@router.get("/study-plans")
def my_plans(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    status: PlanStatus | None = None,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return Response.success(data=service.get_plan_page(db, user.id, page, page_size, status))


@router.get("/plans")
def legacy_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=service.list_plans(db, user.id))


@router.post("/study-plans")
@router.post("/plans", include_in_schema=False)
def save(data: PlanRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=service.save_plan(db, user.id, data))


@router.delete("/study-plans/{plan_id}")
@router.delete("/plans/{plan_id}", include_in_schema=False)
def delete(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.delete_plan(db, user.id, plan_id)
    return Response.success()


@router.patch("/study-plans/{plan_id}")
@router.patch("/plans/{plan_id}", include_in_schema=False)
def update_status(plan_id: int, data: PlanStatusRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.update_status(db, user.id, plan_id, data.status)
    return Response.success()
