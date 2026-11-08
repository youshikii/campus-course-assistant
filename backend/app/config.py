from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent  # 后端项目的根路径


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-flash"
    LLM_EXTRA_BODY: dict = Field(default_factory=dict)
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    CHROMA_HOST: str = "127.0.0.1"
    CHROMA_PORT: int = 8002
    MCP_URL: str = "http://127.0.0.1:8001/mcp"
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = Field(default=8001, ge=1, le=65535)
    MCP_TIMEOUT_SECONDS: float = Field(default=20, gt=0, le=120)
    AGENT_TIMEOUT_SECONDS: int = 180
    AGENT_RECURSION_LIMIT: int = 16

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100M


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}
