"""
SCIM 2.0 (System for Cross-domain Identity Management) Implementation
"""
import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
import json
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SCIMUser, SSOProvider
from core.domain.models import User, Agency
from core.security import get_password_hash

logger = logging.getLogger(__name__)


class SCIMService:
    """SCIM 2.0 Service for user provisioning"""
    
    SCIM_SCHEMAS = {
        "user": "urn:ietf:params:scim:schemas:core:2.0:User",
        "enterprise": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        "list": "urn:ietf:params:scim:api:messages:2.0:ListResponse",
        "error": "urn:ietf:params:scim:api:messages:2.0:Error"
    }
    
    def __init__(self, provider: SSOProvider):
        self.provider = provider
    
    async def create_user(
        self,
        db: AsyncSession,
        scim_user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new user via SCIM"""
        try:
            # Validate required fields
            if not scim_user_data.get('userName'):
                raise ValueError("userName is required")
            
            # Check if user already exists
            existing = await self._find_user_by_username(
                db, 
                scim_user_data['userName']
            )
            if existing:
                raise ValueError(f"User {scim_user_data['userName']} already exists")
            
            # Map SCIM data to user model
            user_data = self._map_scim_to_user(scim_user_data)
            
            # Create user
            user = User(
                id=uuid4(),
                email=user_data['email'],
                username=user_data['username'],
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                hashed_password=get_password_hash(self._generate_temp_password()),
                is_active=user_data.get('active', True),
                agency_id=self.provider.agency_id,
                role=self.provider.default_role or 'fan',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(user)
            
            # Create SCIM user record
            scim_user = SCIMUser(
                user_id=user.id,
                provider_id=self.provider.id,
                external_id=scim_user_data.get('externalId', str(user.id)),
                scim_id=str(user.id),
                schemas=scim_user_data.get('schemas', [self.SCIM_SCHEMAS['user']]),
                last_synced=datetime.utcnow(),
                sync_status='active'
            )
            
            db.add(scim_user)
            await db.commit()
            
            # Return SCIM response
            return self._user_to_scim_response(user, scim_user)
            
        except Exception as e:
            logger.error(f"SCIM user creation failed: {str(e)}")
            await db.rollback()
            raise
    
    async def get_user(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """Get user by SCIM ID"""
        # Find SCIM user record
        result = await db.execute(
            select(SCIMUser, User).join(User).where(
                and_(
                    SCIMUser.scim_id == user_id,
                    SCIMUser.provider_id == self.provider.id
                )
            )
        )
        row = result.first()
        
        if not row:
            raise ValueError(f"User {user_id} not found")
        
        scim_user, user = row
        return self._user_to_scim_response(user, scim_user)
    
    async def update_user(
        self,
        db: AsyncSession,
        user_id: str,
        scim_user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update user via SCIM"""
        try:
            # Find user
            result = await db.execute(
                select(SCIMUser, User).join(User).where(
                    and_(
                        SCIMUser.scim_id == user_id,
                        SCIMUser.provider_id == self.provider.id
                    )
                )
            )
            row = result.first()
            
            if not row:
                raise ValueError(f"User {user_id} not found")
            
            scim_user, user = row
            
            # Map and update user data
            user_data = self._map_scim_to_user(scim_user_data)
            
            if 'email' in user_data:
                user.email = user_data['email']
            if 'username' in user_data:
                user.username = user_data['username']
            if 'first_name' in user_data:
                user.first_name = user_data['first_name']
            if 'last_name' in user_data:
                user.last_name = user_data['last_name']
            if 'active' in user_data:
                user.is_active = user_data['active']
            
            user.updated_at = datetime.utcnow()
            
            # Update SCIM record
            scim_user.last_synced = datetime.utcnow()
            if 'externalId' in scim_user_data:
                scim_user.external_id = scim_user_data['externalId']
            
            await db.commit()
            
            return self._user_to_scim_response(user, scim_user)
            
        except Exception as e:
            logger.error(f"SCIM user update failed: {str(e)}")
            await db.rollback()
            raise
    
    async def delete_user(
        self,
        db: AsyncSession,
        user_id: str
    ) -> None:
        """Delete (deactivate) user via SCIM"""
        try:
            # Find user
            result = await db.execute(
                select(SCIMUser, User).join(User).where(
                    and_(
                        SCIMUser.scim_id == user_id,
                        SCIMUser.provider_id == self.provider.id
                    )
                )
            )
            row = result.first()
            
            if not row:
                raise ValueError(f"User {user_id} not found")
            
            scim_user, user = row
            
            # Soft delete - deactivate user
            user.is_active = False
            user.updated_at = datetime.utcnow()
            
            # Update SCIM record
            scim_user.sync_status = 'deleted'
            scim_user.last_synced = datetime.utcnow()
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"SCIM user deletion failed: {str(e)}")
            await db.rollback()
            raise
    
    async def list_users(
        self,
        db: AsyncSession,
        filter_query: Optional[str] = None,
        start_index: int = 1,
        count: int = 100
    ) -> Dict[str, Any]:
        """List users with SCIM filtering"""
        query = select(SCIMUser, User).join(User).where(
            SCIMUser.provider_id == self.provider.id
        )
        
        # Apply filter if provided
        if filter_query:
            # Simple filter parsing - in production use proper SCIM filter parser
            if 'userName eq' in filter_query:
                username = filter_query.split('"')[1]
                query = query.where(User.username == username)
            elif 'email eq' in filter_query:
                email = filter_query.split('"')[1]
                query = query.where(User.email == email)
            elif 'externalId eq' in filter_query:
                external_id = filter_query.split('"')[1]
                query = query.where(SCIMUser.external_id == external_id)
        
        # Get total count
        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total_results = count_result.scalar()
        
        # Apply pagination
        query = query.offset(start_index - 1).limit(count)
        
        result = await db.execute(query)
        users = []
        
        for scim_user, user in result:
            users.append(self._user_to_scim_response(user, scim_user))
        
        return {
            "schemas": [self.SCIM_SCHEMAS['list']],
            "totalResults": total_results,
            "startIndex": start_index,
            "itemsPerPage": count,
            "Resources": users
        }
    
    async def get_service_provider_config(self) -> Dict[str, Any]:
        """Get SCIM service provider configuration"""
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
    
    async def get_schemas(self) -> List[Dict[str, Any]]:
        """Get supported SCIM schemas"""
        return [
            {
                "id": self.SCIM_SCHEMAS['user'],
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
                        "name": "email",
                        "type": "string",
                        "multiValued": False,
                        "required": True,
                        "caseExact": False,
                        "mutability": "readWrite",
                        "returned": "default",
                        "uniqueness": "server"
                    },
                    {
                        "name": "name",
                        "type": "complex",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "default",
                        "subAttributes": [
                            {"name": "givenName", "type": "string"},
                            {"name": "familyName", "type": "string"}
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
    
    def _map_scim_to_user(self, scim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map SCIM user data to internal user format"""
        user_data = {
            'username': scim_data.get('userName'),
            'email': scim_data.get('emails', [{}])[0].get('value') if scim_data.get('emails') else scim_data.get('email'),
            'active': scim_data.get('active', True)
        }
        
        # Handle name
        if 'name' in scim_data:
            name = scim_data['name']
            user_data['first_name'] = name.get('givenName', '')
            user_data['last_name'] = name.get('familyName', '')
        
        # Apply custom attribute mapping
        if self.provider.attribute_mapping:
            for internal_key, scim_path in self.provider.attribute_mapping.items():
                value = self._get_nested_value(scim_data, scim_path)
                if value is not None:
                    user_data[internal_key] = value
        
        return user_data
    
    def _user_to_scim_response(
        self,
        user: User,
        scim_user: SCIMUser
    ) -> Dict[str, Any]:
        """Convert user to SCIM response format"""
        return {
            "schemas": scim_user.schemas or [self.SCIM_SCHEMAS['user']],
            "id": scim_user.scim_id,
            "externalId": scim_user.external_id,
            "userName": user.username,
            "name": {
                "givenName": user.first_name,
                "familyName": user.last_name
            },
            "emails": [{
                "value": user.email,
                "primary": True
            }],
            "active": user.is_active,
            "meta": {
                "resourceType": "User",
                "created": user.created_at.isoformat() + 'Z',
                "lastModified": user.updated_at.isoformat() + 'Z',
                "location": f"/scim/v2/Users/{scim_user.scim_id}"
            }
        }
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dict using dot notation"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
                
        return value
    
    def _generate_temp_password(self) -> str:
        """Generate temporary password for SCIM users"""
        import random
        import string
        
        length = 16
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))
    
    async def _find_user_by_username(
        self,
        db: AsyncSession,
        username: str
    ) -> Optional[User]:
        """Find user by username"""
        result = await db.execute(
            select(User).where(
                and_(
                    User.username == username,
                    User.agency_id == self.provider.agency_id
                )
            )
        )
        return result.scalar_one_or_none()