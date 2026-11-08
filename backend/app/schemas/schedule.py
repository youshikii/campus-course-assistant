from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScheduleRequest(BaseModel):
    student_id: int = Field(gt=0)
    course_id: int = Field(gt=0)
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    start_date: date
    end_date: date
    location: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=4000)

    @field_validator("start_time", "end_time")
    @classmethod
    def local_time_only(cls, value: time):
        if value.tzinfo is not None:
            raise ValueError("请使用不带时区的北京时间")
        return value

    @model_validator(mode="after")
    def valid_slot(self):
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        delta = (self.weekday - self.start_date.isoweekday()) % 7
        if (self.end_date - self.start_date).days < delta:
            raise ValueError("有效日期范围内没有选定的上课日")
        return self


class ScheduleResponse(BaseModel):
    id: int
    course_id: int
    name: str
    teacher: str
    weekday: int
    start_time: time
    end_time: time
    start_date: date
    end_date: date
    location: str
    notes: str
    model_config = ConfigDict(from_attributes=True)


class AdminScheduleResponse(ScheduleResponse):
    student_id: int
    username: str
    student_name: str
    create_time: datetime
    update_time: datetime


class MCPSchedulesResponse(BaseModel):
    schedules: list[ScheduleResponse]
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def matching_total(self):
        if self.total != len(self.schedules):
            raise ValueError("课表总数与列表不一致")
        return self
