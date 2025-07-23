from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    PROJECT_NAME: str = "AgencyDark"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    REDIS_URL: str = Field(..., env="REDIS_URL")
    REDIS_TTL: int = 3600  # 1 hour default TTL
    
    INFLOW_API_KEY: Optional[str] = Field(None, env="INFLOW_API_KEY")
    INFLOW_API_URL: str = "https://api.inflow.com"
    INFLOW_RATE_LIMIT: int = 100  # requests per minute
    
    FRONTEND_URL: str = Field("http://localhost:3000", env="FRONTEND_URL")
    ALLOWED_ORIGINS: List[str] = []
    
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    
    SENTRY_DSN: Optional[str] = None
    
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    
    UPLOAD_DIR: str = Field("uploads", env="UPLOAD_DIR")
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str], values: dict) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return [values.get("FRONTEND_URL", "http://localhost:3000")]
    
    @validator("DATABASE_URL", pre=True)
    def validate_postgres_url(cls, v: str) -> str:
        if not v.startswith("postgresql://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()