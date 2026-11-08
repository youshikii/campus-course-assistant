from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.files import router as files_router
from app.api.campus import router as campus_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.course import router as course_router
from app.api.schedule import router as schedule_router, admin_router as admin_schedule_router
from app.api.study_plan import router as study_plan_router
from app.api.mcp import router as mcp_router
from app.api.kb_documents import router as kb_documents_router

api = APIRouter(prefix="/api")

api.include_router(auth_router)
api.include_router(user_router)
api.include_router(files_router)
api.include_router(campus_router)
api.include_router(documents_router)
api.include_router(chat_router)
api.include_router(course_router)
api.include_router(schedule_router)
api.include_router(admin_schedule_router)
api.include_router(study_plan_router)
api.include_router(mcp_router)
api.include_router(kb_documents_router)
