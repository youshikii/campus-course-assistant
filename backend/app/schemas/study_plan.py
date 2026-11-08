from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

PlanStatus = Literal["pending", "completed"]


class PlanRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10000)
    target_date: date | None = None

    @field_validator("title", "content")
    @classmethod
    def nonblank_text(cls, value: str, info: ValidationInfo):
        if not value.strip():
            raise ValueError("标题和内容不能只包含空白")
        return value.strip() if info.field_name == "title" else value


class PlanStatusRequest(BaseModel):
    status: PlanStatus


class PlanResponse(BaseModel):
    id: int
    title: str
    content: str
    target_date: date | None = None
    status: PlanStatus
    create_time: datetime
    update_time: datetime
    model_config = ConfigDict(from_attributes=True)
