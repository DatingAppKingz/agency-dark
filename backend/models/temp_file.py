"""Temporary file model."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
from models.base import BaseModel


class TempFile(BaseModel):
    """Temporary file tracking."""
    
    __tablename__ = "temp_files"
    
    # File details
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String, nullable=True)
    
    # User who created it
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User")
    
    # Purpose
    purpose = Column(String, nullable=True)  # upload, export, processing
    
    def __repr__(self):
        return f"<TempFile {self.file_path}>"