"""Run separately: python -m app.mcp_server. All tools derive identity from JWT."""
from datetime import date

import jwt
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.schemas.campus import PlanRequest
from app.services import rag_service, schedule_service, study_plan_service
from app.utils.mcp_auth import user_id_from_authorization


def current_user_id(db) -> int:
    authorization = get_http_headers(include_all=True).get("authorization", "")
    return authenticated_user_id(db, authorization)


def authenticated_user_id(db, authorization: str) -> int:
    user = db.get(User, user_id_from_authorization(authorization))
    if user is None or user.status != 1:
        raise ValueError("登录已失效或账号已禁用")
    return user.id


mcp = FastMCP("校园课程智能助手", mask_error_details=True)


@mcp.tool()
def get_my_schedules(on_date: date | None = None) -> dict:
    """查询当前用户的课程课表。on_date 可选，格式 YYYY-MM-DD；省略则列出所有课程及每周上课时间。"""
    with SessionLocal() as db:
        rows = schedule_service.get_my_schedules(db, current_user_id(db), on_date)
        schedules = [schedule_service.schedule_to_dict(row) for row in rows]
        return {"schedules": schedules, "total": len(schedules)}


@mcp.tool()
def query_schedule(on_date: date | None = None) -> dict:
    """兼容旧版课表查询；新调用请优先使用 get_my_schedules，日期格式 YYYY-MM-DD。"""
    with SessionLocal() as db:
        return {"courses": [schedule_service.schedule_to_dict(row) for row in
                schedule_service.get_my_schedules(db, current_user_id(db), on_date)]}


@mcp.tool()
def search_materials(query: str, course_id: int | None = None, limit: int = 5) -> dict:
    """检索当前用户上传的课程资料。返回原文片段与 citation 标识，回答必须据此引用，不得编造原文。"""
    with SessionLocal() as db:
        return {"sources": rag_service.search_documents(db, current_user_id(db), query, course_id, limit)}


@mcp.tool()
def list_study_plans(page: int = 1, page_size: int = 10) -> dict:
    """分页查询当前用户的学习计划和完成状态，按创建时间倒序。每页 1–100 条。"""
    with SessionLocal() as db:
        result = study_plan_service.get_plan_page(db, current_user_id(db), page, page_size)
        return {"plans": [plan.model_dump(mode="json") for plan in result.list],
                "total": result.total, "page": page, "page_size": page_size}


@mcp.tool()
def save_study_plan(title: str, content: str, target_date: str | None = None) -> dict:
    """保存当前用户明确要求保存的学习计划。仅提出建议或询问时不要调用；计划默认待完成，不会执行外部操作。"""
    data = PlanRequest(title=title, content=content, target_date=target_date)
    with SessionLocal() as db:
        return {"plan": study_plan_service.save_plan(db, current_user_id(db), data).model_dump(mode="json")}


class ToolAuthMiddleware:
    """Authenticate discovery and tool calls, without state shared between users."""

    def __init__(self, app):
        self.app = app

    @staticmethod
    def authenticate(authorization):
        with SessionLocal() as db:
            authenticated_user_id(db, authorization)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            authorization = dict(scope.get("headers", [])).get(b"authorization", b"").decode("latin-1")
            try:
                await run_in_threadpool(self.authenticate, authorization)
            except (jwt.PyJWTError, ValueError):
                response = JSONResponse({"error": "需要有效的登录凭证或 MCP 凭证"}, status_code=401,
                                        headers={"WWW-Authenticate": "Bearer"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# Middleware leaves lifespan messages intact so FastMCP can manage its task groups.
from starlette.middleware import Middleware

app = mcp.http_app(stateless_http=True, middleware=[Middleware(ToolAuthMiddleware)])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.MCP_HOST, port=settings.MCP_PORT)
