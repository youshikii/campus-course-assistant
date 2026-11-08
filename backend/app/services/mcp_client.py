"""Request-scoped MCP calls. Credentials and tools are never cached globally."""
import asyncio
import json
from datetime import date

import httpx
from fastapi import HTTPException
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import settings
from app.schemas.schedule import MCPSchedulesResponse


def _causes(exc: Exception):
    if isinstance(exc, ExceptionGroup):
        for child in exc.exceptions:
            yield from _causes(child)
    else:
        yield exc


def _raise_mcp_error(exc: Exception):
    causes = list(_causes(exc))
    if any(isinstance(cause, (TimeoutError, httpx.TimeoutException)) for cause in causes):
        raise HTTPException(504, "MCP 课表查询超时，请稍后重试") from None
    if any(isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code in (401, 403)
           for cause in causes):
        raise HTTPException(401, "MCP 登录凭证无效，请重新登录") from None
    if any(isinstance(cause, httpx.TransportError) for cause in causes):
        raise HTTPException(503, "MCP 服务暂不可用，请确认独立服务已启动") from None
    raise HTTPException(502, "MCP 课表工具调用失败，请检查服务版本和配置") from None


async def get_schedule_tools(authorization: str):
    """Load only the read-only schedule tool; its connection carries this JWT."""
    try:
        async with asyncio.timeout(settings.MCP_TIMEOUT_SECONDS):
            client = MultiServerMCPClient({"campus": {
                "transport": "http", "url": settings.MCP_URL,
                "headers": {"Authorization": authorization},
            }})
            tools = [tool for tool in await client.get_tools() if tool.name == "get_my_schedules"]
            if not tools:
                raise ValueError("Schedule tool unavailable")
            return tools
    except Exception as exc:
        _raise_mcp_error(exc)


async def get_my_schedules(authorization: str, on_date: date | None = None) -> MCPSchedulesResponse:
    """Discover and call only get_my_schedules with this request's exact header."""
    try:
        async with asyncio.timeout(settings.MCP_TIMEOUT_SECONDS):
            tools = await get_schedule_tools(authorization)
            tool = tools[0]
            arguments = {"on_date": on_date.isoformat()} if on_date else {}
            message = await tool.ainvoke({"type": "tool_call", "id": "schedules",
                                         "name": tool.name, "args": arguments})
            if message.status == "error":
                raise ValueError("Schedule tool failed")
            data = message.artifact.get("structured_content") if isinstance(message.artifact, dict) else None
            if data is None:
                content = message.content
                text = content if isinstance(content, str) else "".join(
                    block.get("text", "") for block in content if block.get("type") == "text"
                )
                data = json.loads(text)
            return MCPSchedulesResponse.model_validate(data)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_mcp_error(exc)
