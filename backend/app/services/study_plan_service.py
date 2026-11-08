from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.response import PageResponse
from app.models.study_plan import StudyPlan
from app.schemas.study_plan import PlanRequest, PlanResponse, PlanStatus


def _query(user_id: int, status: PlanStatus | None = None):
    query = select(StudyPlan).where(StudyPlan.user_id == user_id)
    if status is not None:
        query = query.where(StudyPlan.status == status)
    return query


def _ordered(query):
    return query.order_by(StudyPlan.create_time.desc(), StudyPlan.id.desc())


def get_plan_page(
    db: Session, user_id: int, page: int = 1, page_size: int = 10,
    status: PlanStatus | None = None,
) -> PageResponse:
    # Also validate direct MCP calls, which do not pass through REST Query validation.
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(422, "页码必须大于 0，每页数量必须为 1–100")
    query = _query(user_id, status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(_ordered(query).offset((page - 1) * page_size).limit(page_size)).all()
    return PageResponse(list=[PlanResponse.model_validate(row) for row in rows], total=total)


def list_plans(db: Session, user_id: int):
    """Compatibility for the original unpaginated /api/plans endpoint."""
    rows = db.scalars(_ordered(_query(user_id))).all()
    return [PlanResponse.model_validate(row) for row in rows]


def save_plan(db: Session, user_id: int, data: PlanRequest) -> PlanResponse:
    # user_id is supplied by the authenticated caller, never taken from request data.
    row = StudyPlan(user_id=user_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return PlanResponse.model_validate(row)


def _owned_plan(db: Session, user_id: int, plan_id: int):
    row = db.scalar(select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.user_id == user_id))
    if row is None:
        raise HTTPException(404, "计划不存在")
    return row


def delete_plan(db: Session, user_id: int, plan_id: int):
    db.delete(_owned_plan(db, user_id, plan_id))
    db.commit()


def update_status(db: Session, user_id: int, plan_id: int, status: PlanStatus):
    row = _owned_plan(db, user_id, plan_id)
    row.status = status
    db.commit()
