from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CourseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    teacher: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=100)
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    start_date: date
    end_date: date
    notes: str = Field(default="", max_length=4000)

    @field_validator("start_time", "end_time")
    @classmethod
    def local_time_only(cls, value: time):
        if value.tzinfo is not None:
            raise ValueError("请使用不带时区的北京时间")
        return value

    @model_validator(mode="after")
    def validate_schedule(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("课程名称不能为空")
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        if self.end_date < self.start_date:
            raise ValueError("课程结束日期不能早于开始日期")
        return self


class CourseResponse(CourseRequest):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AdminCourseRequest(CourseRequest):
    user_id: int = Field(gt=0)


class AdminCourseResponse(CourseResponse):
    user_id: int
    username: str
    user_name: str
    create_time: datetime
    update_time: datetime
