"""
Simplified chat endpoints that work with current authentication.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import CurrentUser
from models.user import UserRole
from models.chat import Conversation, Message, ChatTemplate

router = APIRouter(prefix="/chat", tags=["chat"])


class ConversationListResponse(BaseModel):
    conversations: List[dict]
    total: int


class TemplateListResponse(BaseModel):
    templates: List[dict]
    total: int


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """
    List conversations (simplified).
    Returns empty list for now as conversations need proper model setup.
    """
    user_role = current_user.get("role")
    user_id = current_user.get("user_id")
    
    # For now, return empty list as we need proper model relationships
    return ConversationListResponse(
        conversations=[],
        total=0
    )


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    List chat templates for the agency.
    Returns empty list for now.
    """
    agency_id = current_user.get("agency_id")
    
    # For now, return empty list
    return TemplateListResponse(
        templates=[],
        total=0
    )