"""
API configuration management
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, SecretStr
from datetime import datetime
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer


class APICredentials(BaseModel):
    """API credentials model"""
    api_key: Optional[SecretStr] = None
    api_secret: Optional[SecretStr] = None
    access_token: Optional[SecretStr] = None
    refresh_token: Optional[SecretStr] = None
    client_id: Optional[str] = None
    client_secret: Optional[SecretStr] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    
    def get_secret_value(self, field: str) -> Optional[str]:
        """Safely get secret value"""
        value = getattr(self, field, None)
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return value
    
    class Config:
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None
        }


class APIConfig(BaseModel):
    """API configuration model"""
    name: str
    base_url: str
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    rate_limit: Optional[int] = Field(None, description="Requests per minute")
    credentials: Optional[APICredentials] = None
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    webhook_url: Optional[str] = None
    is_active: bool = True
    
    @classmethod
    def from_env(cls, prefix: str) -> 'APIConfig':
        """Create config from environment variables"""
        # Base configuration
        config_data = {
            'name': os.getenv(f"{prefix}_NAME", prefix),
            'base_url': os.getenv(f"{prefix}_BASE_URL", ""),
            'timeout': int(os.getenv(f"{prefix}_TIMEOUT", "30")),
            'max_retries': int(os.getenv(f"{prefix}_MAX_RETRIES", "3")),
            'rate_limit': int(os.getenv(f"{prefix}_RATE_LIMIT", "0")) or None,
            'webhook_url': os.getenv(f"{prefix}_WEBHOOK_URL"),
            'is_active': os.getenv(f"{prefix}_ACTIVE", "true").lower() == "true"
        }
        
        # Credentials
        creds_data = {}
        for field in ['api_key', 'api_secret', 'access_token', 'refresh_token',
                      'client_id', 'client_secret', 'username', 'password']:
            value = os.getenv(f"{prefix}_{field.upper()}")
            if value:
                if field in ['api_key', 'api_secret', 'access_token', 'refresh_token', 
                           'client_secret', 'password']:
                    creds_data[field] = SecretStr(value)
                else:
                    creds_data[field] = value
                    
        if creds_data:
            config_data['credentials'] = APICredentials(**creds_data)
            
        # Custom headers
        headers = {}
        header_prefix = f"{prefix}_HEADER_"
        for key, value in os.environ.items():
            if key.startswith(header_prefix):
                header_name = key[len(header_prefix):].lower().replace('_', '-')
                headers[header_name] = value
                
        if headers:
            config_data['custom_headers'] = headers
            
        return cls(**config_data)


class APIConfigModel(Base):
    """Database model for API configurations"""
    __tablename__ = "api_configs"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    base_url = Column(String, nullable=False)
    timeout = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    rate_limit = Column(Integer, nullable=True)
    credentials = Column(Text, nullable=True)  # Encrypted JSON
    custom_headers = Column(Text, default="{}")  # JSON
    webhook_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_config(self, encryption_key: Optional[str] = None) -> APIConfig:
        """Convert database model to APIConfig"""
        from core.security import decrypt_data
        
        config_data = {
            'name': self.name,
            'base_url': self.base_url,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'rate_limit': self.rate_limit,
            'webhook_url': self.webhook_url,
            'is_active': self.is_active
        }
        
        # Decrypt and parse credentials
        if self.credentials and encryption_key:
            try:
                decrypted = decrypt_data(self.credentials, encryption_key)
                creds_data = json.loads(decrypted)
                config_data['credentials'] = APICredentials(**creds_data)
            except Exception:
                pass  # Skip if decryption fails
                
        # Parse custom headers
        if self.custom_headers:
            try:
                config_data['custom_headers'] = json.loads(self.custom_headers)
            except json.JSONDecodeError:
                config_data['custom_headers'] = {}
                
        return APIConfig(**config_data)
    
    @classmethod
    def from_config(cls, config: APIConfig, encryption_key: Optional[str] = None) -> 'APIConfigModel':
        """Create database model from APIConfig"""
        from core.security import encrypt_data
        import uuid
        
        model = cls(
            id=str(uuid.uuid4()),
            name=config.name,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
            rate_limit=config.rate_limit,
            webhook_url=config.webhook_url,
            is_active=config.is_active,
            custom_headers=json.dumps(config.custom_headers)
        )
        
        # Encrypt credentials
        if config.credentials and encryption_key:
            creds_dict = config.credentials.model_dump()
            # Convert SecretStr to actual values
            for key, value in creds_dict.items():
                if isinstance(value, SecretStr):
                    creds_dict[key] = value.get_secret_value()
                    
            encrypted = encrypt_data(json.dumps(creds_dict), encryption_key)
            model.credentials = encrypted
            
        return model


class APIConfigManager:
    """Manager for API configurations"""
    
    def __init__(self, db: AsyncSession, encryption_key: Optional[str] = None):
        self.db = db
        self.encryption_key = encryption_key or os.getenv('ENCRYPTION_KEY')
        self._cache: Dict[str, APIConfig] = {}
        
    async def get_config(self, name: str) -> Optional[APIConfig]:
        """Get API configuration by name"""
        # Check cache first
        if name in self._cache:
            return self._cache[name]
            
        # Try environment variables
        env_prefixes = {
            'inflow': 'INFLOW',
            'onlyfans': 'ONLYFANS',
            'stripe': 'STRIPE',
            'paypal': 'PAYPAL'
        }
        
        if name.lower() in env_prefixes:
            config = APIConfig.from_env(env_prefixes[name.lower()])
            if config.base_url:  # Valid config
                self._cache[name] = config
                return config
                
        # Try database
        result = await self.db.execute(
            select(APIConfigModel).where(
                APIConfigModel.name == name,
                APIConfigModel.is_active == True
            )
        )
        model = result.scalar_one_or_none()
        
        if model:
            config = model.to_config(self.encryption_key)
            self._cache[name] = config
            return config
            
        return None
        
    async def save_config(self, config: APIConfig) -> APIConfigModel:
        """Save API configuration to database"""
        # Check if exists
        result = await self.db.execute(
            select(APIConfigModel).where(APIConfigModel.name == config.name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.base_url = config.base_url
            existing.timeout = config.timeout
            existing.max_retries = config.max_retries
            existing.rate_limit = config.rate_limit
            existing.webhook_url = config.webhook_url
            existing.is_active = config.is_active
            existing.custom_headers = json.dumps(config.custom_headers)
            existing.updated_at = datetime.utcnow()
            
            if config.credentials and self.encryption_key:
                from core.security import encrypt_data
                creds_dict = config.credentials.model_dump()
                encrypted = encrypt_data(json.dumps(creds_dict), self.encryption_key)
                existing.credentials = encrypted
                
            model = existing
        else:
            # Create new
            model = APIConfigModel.from_config(config, self.encryption_key)
            self.db.add(model)
            
        await self.db.commit()
        
        # Update cache
        self._cache[config.name] = config
        
        return model
        
    async def delete_config(self, name: str) -> bool:
        """Delete API configuration"""
        result = await self.db.execute(
            select(APIConfigModel).where(APIConfigModel.name == name)
        )
        model = result.scalar_one_or_none()
        
        if model:
            await self.db.delete(model)
            await self.db.commit()
            
            # Remove from cache
            self._cache.pop(name, None)
            
            return True
            
        return False
        
    async def list_configs(self) -> list[APIConfig]:
        """List all active API configurations"""
        result = await self.db.execute(
            select(APIConfigModel).where(APIConfigModel.is_active == True)
        )
        models = result.scalars().all()
        
        configs = []
        for model in models:
            config = model.to_config(self.encryption_key)
            configs.append(config)
            self._cache[config.name] = config
            
        return configs
        
    def clear_cache(self):
        """Clear configuration cache"""
        self._cache.clear()