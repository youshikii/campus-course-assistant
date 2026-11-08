import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update

from app.config import settings
from app.database import SessionLocal
from app.models.campus import ChatMessage, ChatSession
from app.services.campus_service import owned


def session_info(row):
    return {"id": row.id, "title": row.title, "create_time": row.create_time.isoformat()}


def list_sessions(user_id: int):
    with SessionLocal() as db:
        rows = db.scalars(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.id.desc())).all()
        return [session_info(row) for row in rows]


def create_session(user_id: int):
    with SessionLocal() as db:
        row = ChatSession(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return session_info(row)


def get_messages(user_id: int, session_id: int):
    with SessionLocal() as db:
        owned(db, ChatSession, session_id, user_id)
        rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)).all()
        return [{"id": row.id, "role": row.role, "content": row.content,
                 "sources": row.sources, "events": row.events} for row in rows]


def acquire_run(user_id: int, session_id: int, message: str):
    token, now = str(uuid4()), int(time.time())
    with SessionLocal() as db:
        row = owned(db, ChatSession, session_id, user_id)
        if not message.strip():
            raise HTTPException(422, "消息不能为空")
        result = db.execute(update(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id,
            or_(ChatSession.run_token.is_(None), ChatSession.run_started_at < now - settings.AGENT_TIMEOUT_SECONDS - 30),
        ).values(run_token=token, run_started_at=now))
        if result.rowcount != 1:
            raise HTTPException(409, "该对话正在生成回答，请等待完成或停止后再试")
        rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(20)).all()
        history = [{"role": item.role, "content": item.content} for item in reversed(rows)]
        history.append({"role": "user", "content": message})
        db.add(ChatMessage(session_id=session_id, role="user", content=message))
        if row.title == "新对话":
            row.title = message.strip()[:40]
        db.commit()
    return token, history


def finish_run(session_id: int, token: str, content: str, sources: list, events: list):
    with SessionLocal() as db:
        # A timed-out old worker cannot overwrite a newer run.
        result = db.execute(update(ChatSession).where(
            ChatSession.id == session_id, ChatSession.run_token == token,
        ).values(run_token=None, run_started_at=0))
        if result.rowcount == 1 and content:
            db.add(ChatMessage(session_id=session_id, role="assistant", content=content,
                               sources=sources, events=events))
        db.commit()


def delete_session(user_id: int, session_id: int):
    with SessionLocal() as db:
        row = owned(db, ChatSession, session_id, user_id)
        if row.run_token and row.run_started_at >= int(time.time()) - settings.AGENT_TIMEOUT_SECONDS - 30:
            raise HTTPException(409, "请先停止该对话的生成任务")
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        db.delete(row)
        db.commit()
