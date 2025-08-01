from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ValidationInfo
from typing import List, Optional, Union
import secrets


class Settings(BaseSettings):
    PROJECT_NAME: str = "AgencyDark"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # Encryption settings
    ENCRYPTION_KEY: str = Field("", env="ENCRYPTION_KEY")
    
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    REDIS_URL: str = Field(..., env="REDIS_URL")
    REDIS_TTL: int = 3600  # 1 hour default TTL
    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_DB: int = Field(0, env="REDIS_DB")
    
    INFLOW_API_KEY: Optional[str] = Field(None, env="INFLOW_API_KEY")
    INFLOW_API_URL: str = "https://api.inflow.com"
    INFLOW_RATE_LIMIT: int = 100  # requests per minute
    
    FRONTEND_URL: str = Field("http://localhost:3000", env="FRONTEND_URL")
    ALLOWED_ORIGINS: Union[str, List[str]] = Field(default="", env="ALLOWED_ORIGINS")
    
    # Email configuration
    SMTP_HOST: str = Field("localhost", env="SMTP_HOST")
    SMTP_PORT: int = Field(587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(True, env="SMTP_USE_TLS")
    FROM_EMAIL: str = Field("noreply@agencydark.com", env="FROM_EMAIL")
    FROM_NAME: str = Field("AgencyDark", env="FROM_NAME")
    
    SENTRY_DSN: Optional[str] = None
    
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    HOSTNAME: str = Field("localhost", env="HOSTNAME")
    
    UPLOAD_DIR: str = Field("uploads", env="UPLOAD_DIR")
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    
    # Encryption
    ENCRYPTION_KEY: Optional[str] = Field(None, env="ENCRYPTION_KEY")
    API_KEY_SALT: str = Field(default_factory=lambda: secrets.token_urlsafe(16), env="API_KEY_SALT")
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str], None], info: ValidationInfo) -> List[str]:
        if v is None or v == "":
            # Get FRONTEND_URL from the data being validated
            frontend_url = info.data.get("FRONTEND_URL", "http://localhost:3000")
            return [frontend_url]
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        # Fallback
        frontend_url = info.data.get("FRONTEND_URL", "http://localhost:3000")
        return [frontend_url]
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        if not (v.startswith("postgresql://") or v.startswith("postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    # Additional fields from .env
    APP_NAME: Optional[str] = Field("AgencyDark", env="APP_NAME")
    APP_VERSION: Optional[str] = Field("1.0.0", env="APP_VERSION")
    DATABASE_SYNC_URL: Optional[str] = Field(None, env="DATABASE_SYNC_URL")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    JWT_SECRET_KEY: Optional[str] = Field(None, env="JWT_SECRET_KEY")
    JWT_ALGORITHM: Optional[str] = Field("HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Optional[int] = Field(30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: Optional[int] = Field(7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    SMTP_FROM: Optional[str] = Field(None, env="SMTP_FROM")
    ALLOWED_HOSTS: Optional[str] = Field("localhost,127.0.0.1", env="ALLOWED_HOSTS")
    UPLOAD_DIR: Optional[str] = Field("./uploads", env="UPLOAD_DIR")
    MAX_UPLOAD_SIZE: Optional[int] = Field(10485760, env="MAX_UPLOAD_SIZE")
    ENVIRONMENT: Optional[str] = Field("development", env="ENVIRONMENT")
    DEBUG: Optional[bool] = Field(False, env="DEBUG")
    SMTP_USER: Optional[str] = Field(None, env="SMTP_USER")
    
    # Logging configuration
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FILE: Optional[str] = Field(None, env="LOG_FILE")
    LOG_FORMAT: str = Field("json", env="LOG_FORMAT")  # "json" or "text"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()