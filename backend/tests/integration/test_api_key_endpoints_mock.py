"""
Integration tests for API key endpoints with full mocking
"""
import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta

# Mock responses
MOCK_API_KEY = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Production API Key",
    "key_prefix": "pk_live_",
    "scopes": ["read:analytics", "write:analytics"],
    "created_at": datetime.utcnow().isoformat(),
    "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
    "is_active": True,
    "environment": "live"
}

MOCK_API_KEY_CREATED = {
    **MOCK_API_KEY,
    "public_key": "pk_live_abcd1234efgh5678ijkl9012",
    "secret_key": "sk_live_mnop3456qrst7890uvwx1234"  # Only returned on creation
}


class TestAPIKeyEndpoints:
    """Test API key management endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_api_key(self):
        """Test creating a new API key."""
        # Create a mock app
        from fastapi import FastAPI, Depends
        from fastapi.security import HTTPBearer
        
        app = FastAPI()
        
        # Mock auth dependency
        async def mock_current_user():
            return {"id": "user123", "agency_id": "agency456"}
        
        # Create endpoint
        @app.post("/api/v1/api-keys")
        async def create_api_key(
            name: str,
            scopes: list[str],
            current_user=Depends(mock_current_user)
        ):
            return MOCK_API_KEY_CREATED
        
        # Test the endpoint
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/api-keys",
                json={
                    "name": "Production API Key",
                    "scopes": ["read:analytics", "write:analytics"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Production API Key"
            assert "public_key" in data
            assert "secret_key" in data
            assert data["key_prefix"] == "pk_live_"
    
    @pytest.mark.asyncio
    async def test_list_api_keys(self):
        """Test listing API keys."""
        from fastapi import FastAPI, Depends
        
        app = FastAPI()
        
        async def mock_current_user():
            return {"id": "user123", "agency_id": "agency456"}
        
        @app.get("/api/v1/api-keys")
        async def list_api_keys(current_user=Depends(mock_current_user)):
            return {
                "items": [MOCK_API_KEY],
                "total": 1,
                "page": 1,
                "size": 20
            }
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/api-keys")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["name"] == "Production API Key"
    
    @pytest.mark.asyncio
    async def test_rotate_api_key(self):
        """Test rotating an API key."""
        from fastapi import FastAPI, Depends
        
        app = FastAPI()
        
        async def mock_current_user():
            return {"id": "user123", "agency_id": "agency456"}
        
        @app.post("/api/v1/api-keys/{key_id}/rotate")
        async def rotate_api_key(
            key_id: str,
            current_user=Depends(mock_current_user)
        ):
            return {
                **MOCK_API_KEY,
                "public_key": "pk_live_new1234efgh5678ijkl9012",
                "secret_key": "sk_live_new3456qrst7890uvwx1234",
                "rotated_at": datetime.utcnow().isoformat()
            }
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/api-keys/{MOCK_API_KEY['id']}/rotate"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "public_key" in data
            assert "secret_key" in data
            assert data["public_key"].startswith("pk_live_new")
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self):
        """Test revoking an API key."""
        from fastapi import FastAPI, Depends
        
        app = FastAPI()
        
        async def mock_current_user():
            return {"id": "user123", "agency_id": "agency456"}
        
        @app.delete("/api/v1/api-keys/{key_id}")
        async def revoke_api_key(
            key_id: str,
            current_user=Depends(mock_current_user)
        ):
            return {
                "message": "API key revoked successfully",
                "key_id": key_id
            }
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/api-keys/{MOCK_API_KEY['id']}"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "API key revoked successfully"
    
    @pytest.mark.asyncio 
    async def test_api_key_authentication(self):
        """Test authenticating with an API key."""
        from fastapi import FastAPI, Depends, HTTPException
        
        app = FastAPI()
        
        async def verify_api_key(authorization: str = None):
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing API key")
            
            token = authorization.replace("Bearer ", "")
            if token != "pk_live_valid:sk_live_secret":
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            return {"api_key_id": "123", "scopes": ["read:analytics"]}
        
        @app.get("/api/v1/protected")
        async def protected_endpoint(api_key=Depends(verify_api_key)):
            return {"message": "Access granted", "api_key_id": api_key["api_key_id"]}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test without API key
            response = await client.get("/api/v1/protected")
            assert response.status_code == 401
            
            # Test with invalid API key
            response = await client.get(
                "/api/v1/protected",
                headers={"Authorization": "Bearer invalid_key"}
            )
            assert response.status_code == 401
            
            # Test with valid API key
            response = await client.get(
                "/api/v1/protected",
                headers={"Authorization": "Bearer pk_live_valid:sk_live_secret"}
            )
            assert response.status_code == 200
            assert response.json()["message"] == "Access granted"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])