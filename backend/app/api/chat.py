import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.common.response import Response
from app.config import settings
from app.dependencies.auth import get_current_authorization, get_current_user
from app.models.user import User
from app.schemas.campus import ChatRequest
from app.services import chat_service
from app.services.agent_service import ask_agent, stream_agent, stream_answer
from app.schemas.chat import ChatAskRequest

router = APIRouter(prefix="/chat", tags=["智能助手"])


@router.post("/ask", summary="ReAct Agent 对话（完整回答）", response_model=Response)
async def ask(data: ChatAskRequest, authorization: str = Depends(get_current_authorization)):
    """接收问题和 user/assistant 历史消息；本次 JWT 决定 MCP 查询身份，不保存会话。"""
    return Response.success(data=await ask_agent(data, authorization))


@router.post("/stream", summary="ReAct Agent SSE 流式对话",
             response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
async def stream_question(data: ChatAskRequest, authorization: str = Depends(get_current_authorization)):
    """返回 status/tool_start/tool_end/token/error/done；仅成功问答应加入下一轮 history。"""
    if not settings.LLM_API_KEY:
        raise HTTPException(503, "请在后端配置 LLM_API_KEY 后使用智能助手")
    return sse_response(stream_answer(data, authorization))


@router.get("/config")
def config(user: User = Depends(get_current_user)):
    return Response.success(data={"model": settings.LLM_MODEL,
        "llm_configured": bool(settings.LLM_API_KEY),
        "embedding_configured": bool(settings.EMBEDDING_API_KEY)})


@router.get("/sessions")
def sessions(user: User = Depends(get_current_user)):
    return Response.success(data=chat_service.list_sessions(user.id))


@router.post("/sessions")
def create_session(user: User = Depends(get_current_user)):
    return Response.success(data=chat_service.create_session(user.id))


@router.get("/sessions/{session_id}/messages")
def messages(session_id: int, user: User = Depends(get_current_user)):
    return Response.success(data=chat_service.get_messages(user.id, session_id))


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user: User = Depends(get_current_user)):
    chat_service.delete_session(user.id, session_id)
    return Response.success()


@router.post("/sessions/{session_id}/stream")
async def stream(session_id: int, data: ChatRequest, user: User = Depends(get_current_user)):
    if not settings.LLM_API_KEY:
        raise HTTPException(503, "请在后端配置 LLM_API_KEY 后使用智能助手")
    token, history = await asyncio.to_thread(chat_service.acquire_run, user.id, session_id, data.message)
    return sse_response(stream_agent(user.id, session_id, token, history))


def sse_response(source):
    """Keep connections alive and cancel the Agent when a client disconnects."""

    async def events():
        pending = None
        try:
            while True:
                if pending is None:
                    pending = asyncio.create_task(anext(source))
                try:
                    name, payload = await asyncio.wait_for(asyncio.shield(pending), timeout=15)
                    pending = None
                    yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
                except StopAsyncIteration:
                    break
        finally:
            if pending:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await source.aclose()

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
