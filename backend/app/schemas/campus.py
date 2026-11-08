from pydantic import BaseModel, Field
from app.schemas.course import CourseRequest, CourseResponse  # Compatible imports.
from app.schemas.study_plan import PlanRequest, PlanStatusRequest, PlanResponse


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    course_id: int | None = None
    limit: int = Field(default=5, ge=1, le=8)
