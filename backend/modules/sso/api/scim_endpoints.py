"""
SCIM 2.0 API Endpoints
"""
from typing import Optional, Dict, Any
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, Body
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_active_user
from ..manager import sso_manager
from ..schemas import (
    SCIMUserRequest,
    SCIMUserResponse,
    SCIMListResponse,
    SCIMErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scim/v2", tags=["scim"])


async def verify_scim_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """Verify SCIM bearer token and return provider ID"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ")[1]
    
    # In production, implement proper token validation
    # For now, we'll assume the token contains the provider ID
    try:
        # This is a simplified example - implement proper token validation
        provider_id = UUID(token)
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider or not provider.is_active:
            raise ValueError("Invalid provider")
        return provider_id
    except:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


def scim_error_response(status: int, detail: str, scim_type: Optional[str] = None) -> JSONResponse:
    """Create SCIM error response"""
    error = SCIMErrorResponse(
        status=str(status),
        detail=detail,
        scimType=scim_type
    )
    return JSONResponse(
        status_code=status,
        content=error.dict(exclude_none=True)
    )


@router.get("/ServiceProviderConfig")
async def get_service_provider_config():
    """Get SCIM service provider configuration"""
    # This doesn't require authentication
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 1000},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Authentication using OAuth 2.0 bearer token"
            }
        ]
    }


@router.get("/Schemas")
async def get_schemas():
    """Get supported SCIM schemas"""
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 1,
        "startIndex": 1,
        "itemsPerPage": 1,
        "Resources": [
            {
                "id": "urn:ietf:params:scim:schemas:core:2.0:User",
                "name": "User",
                "description": "User Account",
                "attributes": [
                    {
                        "name": "userName",
                        "type": "string",
                        "multiValued": False,
                        "required": True,
                        "caseExact": False,
                        "mutability": "readWrite",
                        "returned": "default",
                        "uniqueness": "server"
                    },
                    {
                        "name": "emails",
                        "type": "complex",
                        "multiValued": True,
                        "required": True,
                        "mutability": "readWrite",
                        "returned": "default",
                        "subAttributes": [
                            {
                                "name": "value",
                                "type": "string",
                                "multiValued": False,
                                "required": True
                            },
                            {
                                "name": "primary",
                                "type": "boolean",
                                "multiValued": False,
                                "required": False
                            }
                        ]
                    },
                    {
                        "name": "name",
                        "type": "complex",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "default",
                        "subAttributes": [
                            {
                                "name": "givenName",
                                "type": "string",
                                "multiValued": False,
                                "required": False
                            },
                            {
                                "name": "familyName",
                                "type": "string",
                                "multiValued": False,
                                "required": False
                            }
                        ]
                    },
                    {
                        "name": "active",
                        "type": "boolean",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "default"
                    }
                ]
            }
        ]
    }


@router.post("/Users", response_model=SCIMUserResponse, responses={
    400: {"model": SCIMErrorResponse},
    401: {"model": SCIMErrorResponse},
    409: {"model": SCIMErrorResponse}
})
async def create_user(
    user_data: SCIMUserRequest,
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user via SCIM"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        scim_service = sso_manager.get_scim_service(provider)
        user_response = await scim_service.create_user(db, user_data.dict())
        
        return SCIMUserResponse(**user_response)
        
    except ValueError as e:
        if "already exists" in str(e):
            return scim_error_response(409, str(e), "uniqueness")
        return scim_error_response(400, str(e))
    except Exception as e:
        logger.error(f"SCIM user creation error: {str(e)}")
        return scim_error_response(500, "Internal server error")


@router.get("/Users/{user_id}", response_model=SCIMUserResponse, responses={
    404: {"model": SCIMErrorResponse}
})
async def get_user(
    user_id: str,
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """Get user by SCIM ID"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        scim_service = sso_manager.get_scim_service(provider)
        user_response = await scim_service.get_user(db, user_id)
        
        return SCIMUserResponse(**user_response)
        
    except ValueError as e:
        return scim_error_response(404, str(e))
    except Exception as e:
        logger.error(f"SCIM get user error: {str(e)}")
        return scim_error_response(500, "Internal server error")


@router.put("/Users/{user_id}", response_model=SCIMUserResponse, responses={
    404: {"model": SCIMErrorResponse}
})
async def update_user(
    user_id: str,
    user_data: SCIMUserRequest,
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """Update user via SCIM (full update)"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        scim_service = sso_manager.get_scim_service(provider)
        user_response = await scim_service.update_user(db, user_id, user_data.dict())
        
        return SCIMUserResponse(**user_response)
        
    except ValueError as e:
        return scim_error_response(404, str(e))
    except Exception as e:
        logger.error(f"SCIM update user error: {str(e)}")
        return scim_error_response(500, "Internal server error")


@router.patch("/Users/{user_id}", response_model=SCIMUserResponse, responses={
    404: {"model": SCIMErrorResponse}
})
async def patch_user(
    user_id: str,
    patch_request: Dict[str, Any],
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """Patch user via SCIM (partial update)"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        # Convert SCIM patch to user data update
        # This is a simplified implementation
        user_data = {}
        
        for operation in patch_request.get("Operations", []):
            op = operation.get("op", "").lower()
            path = operation.get("path", "")
            value = operation.get("value")
            
            if op == "replace":
                if path == "active":
                    user_data["active"] = value
                elif path == "userName":
                    user_data["userName"] = value
                elif path.startswith("name."):
                    if "name" not in user_data:
                        user_data["name"] = {}
                    field = path.split(".")[-1]
                    user_data["name"][field] = value
        
        scim_service = sso_manager.get_scim_service(provider)
        user_response = await scim_service.update_user(db, user_id, user_data)
        
        return SCIMUserResponse(**user_response)
        
    except ValueError as e:
        return scim_error_response(404, str(e))
    except Exception as e:
        logger.error(f"SCIM patch user error: {str(e)}")
        return scim_error_response(500, "Internal server error")


@router.delete("/Users/{user_id}")
async def delete_user(
    user_id: str,
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """Delete (deactivate) user via SCIM"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        scim_service = sso_manager.get_scim_service(provider)
        await scim_service.delete_user(db, user_id)
        
        return Response(status_code=204)
        
    except ValueError as e:
        return scim_error_response(404, str(e))
    except Exception as e:
        logger.error(f"SCIM delete user error: {str(e)}")
        return scim_error_response(500, "Internal server error")


@router.get("/Users", response_model=SCIMListResponse)
async def list_users(
    filter: Optional[str] = Query(None),
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=1000),
    provider_id: UUID = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db)
):
    """List users with optional filtering"""
    try:
        provider = await sso_manager.get_provider(db, provider_id)
        if not provider:
            return scim_error_response(404, "Provider not found")
        
        scim_service = sso_manager.get_scim_service(provider)
        response = await scim_service.list_users(db, filter, startIndex, count)
        
        return SCIMListResponse(**response)
        
    except Exception as e:
        logger.error(f"SCIM list users error: {str(e)}")
        return scim_error_response(500, "Internal server error")