from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KBDocumentResponse(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    create_time: datetime
    model_config = ConfigDict(from_attributes=True)
