from datetime import date

from fastapi import APIRouter, Depends

from app.common.response import Response
from app.dependencies.auth import get_current_authorization
from app.services import mcp_client

router = APIRouter(prefix="/mcp", tags=["MCP 课表查询"])


@router.get("/my-schedules", summary="通过 MCP 查询我的课表")
async def my_schedules(
    on_date: date | None = None,
    authorization: str = Depends(get_current_authorization),
):
    """登录后发现并调用 get_my_schedules。只转发 Authorization，不接受用户身份参数。"""
    result = await mcp_client.get_my_schedules(authorization, on_date)
    return Response.success(data=result)
