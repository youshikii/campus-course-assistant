from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str):
        if not value.strip():
            raise ValueError("历史消息不能为空白")
        return value


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=6000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"question": "查询我的全部课表", "history": []},
        {"question": "这些课分别在哪间教室？", "history": [
            {"role": "user", "content": "查询我的全部课表"},
            {"role": "assistant", "content": "这里填写上一轮返回的完整回答"},
        ]},
    ]})

    @field_validator("question")
    @classmethod
    def nonblank(cls, value: str):
        if not value.strip():
            raise ValueError("问题不能为空白")
        return value.strip()

    @model_validator(mode="after")
    def context_size(self):
        if len(self.question) + sum(len(message.content) for message in self.history) > 60000:
            raise ValueError("对话上下文过长，请缩短历史消息")
        return self


class ChatAskResponse(BaseModel):
    answer: str
