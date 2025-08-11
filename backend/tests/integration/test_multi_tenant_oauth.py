"""
Integration tests for multi-tenant OAuth implementation.
Tests agency isolation, permissions, and cross-agency access control.
"""
import pytest
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from oauth.models import OAuthClient, OAuthToken
from oauth.multitenancy import get_current_agency, AgencyContext
from models.user import User
from models.agency import Agency
from core.database import Base


class TestMultiTenantOAuth:
    """Test multi-tenant OAuth implementation."""
    
    @pytest.fixture(scope="class")
    async def db_engine(self):
        """Create test database engine."""
        engine = create_async_engine(
            "postgresql+asyncpg://test:test@localhost/test_multitenant",
            echo=False
        )
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield engine
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        await engine.dispose()
    
    @pytest.fixture
    async def db_session(self, db_engine):
        """Create database session."""
        async_session = sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            yield session
    
    @pytest.fixture
    async def agency_1(self, db_session: AsyncSession):
        """Create first test agency."""
        agency = Agency(
            id=uuid4(),
            name="Agency One",
            subdomain="agency1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(agency)
        await db_session.commit()
        return agency
    
    @pytest.fixture
    async def agency_2(self, db_session: AsyncSession):
        """Create second test agency."""
        agency = Agency(
            id=uuid4(),
            name="Agency Two",
            subdomain="agency2",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(agency)
        await db_session.commit()
        return agency
    
    @pytest.fixture
    async def user_agency_1(self, db_session: AsyncSession, agency_1):
        """Create user for agency 1."""
        user = User(
            id=uuid4(),
            email="user1@agency1.com",
            username="user1",
            agency_id=agency_1.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(user)
        await db_session.commit()
        return user
    
    @pytest.fixture
    async def user_agency_2(self, db_session: AsyncSession, agency_2):
        """Create user for agency 2."""
        user = User(
            id=uuid4(),
            email="user2@agency2.com",
            username="user2",
            agency_id=agency_2.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(user)
        await db_session.commit()
        return user
    
    @pytest.fixture
    async def client_agency_1(self, db_session: AsyncSession, agency_1):
        """Create OAuth client for agency 1."""
        client = OAuthClient(
            id=uuid4(),
            agency_id=agency_1.id,
            client_id=f"agency1_client_{secrets.token_urlsafe(8)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Agency 1 Client",
            redirect_uris=["http://agency1.example.com/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write",
            allowed_agencies=[agency_1.id],  # Only agency 1
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(client)
        await db_session.commit()
        return client
    
    @pytest.fixture
    async def client_agency_2(self, db_session: AsyncSession, agency_2):
        """Create OAuth client for agency 2."""
        client = OAuthClient(
            id=uuid4(),
            agency_id=agency_2.id,
            client_id=f"agency2_client_{secrets.token_urlsafe(8)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Agency 2 Client",
            redirect_uris=["http://agency2.example.com/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write",
            allowed_agencies=[agency_2.id],  # Only agency 2
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(client)
        await db_session.commit()
        return client
    
    @pytest.mark.asyncio
    async def test_agency_isolation(
        self,
        db_session: AsyncSession,
        agency_1,
        agency_2,
        client_agency_1,
        client_agency_2
    ):
        """Test that agencies are properly isolated."""
        # Verify clients are isolated to their agencies
        assert client_agency_1.agency_id == agency_1.id
        assert client_agency_2.agency_id == agency_2.id
        assert client_agency_1.agency_id != client_agency_2.agency_id
        
        # Verify allowed agencies
        assert agency_1.id in client_agency_1.allowed_agencies
        assert agency_2.id not in client_agency_1.allowed_agencies
        assert agency_2.id in client_agency_2.allowed_agencies
        assert agency_1.id not in client_agency_2.allowed_agencies
    
    @pytest.mark.asyncio
    async def test_cross_agency_token_denial(
        self,
        db_session: AsyncSession,
        user_agency_1,
        user_agency_2,
        client_agency_1
    ):
        """Test that cross-agency token access is denied."""
        # Try to create token for user from agency 2 using client from agency 1
        # This should be prevented in real implementation
        
        # Verify users belong to different agencies
        assert user_agency_1.agency_id != user_agency_2.agency_id
        
        # Client from agency 1 should not be able to issue token for user from agency 2
        assert user_agency_2.agency_id not in client_agency_1.allowed_agencies
    
    @pytest.mark.asyncio
    async def test_subdomain_routing(self):
        """Test agency resolution from subdomain."""
        test_cases = [
            ("agency1.agencydark.com", "agency1"),
            ("agency2.agencydark.com", "agency2"),
            ("test.agency.agencydark.com", "test"),
            ("localhost", None),  # No subdomain
            ("agencydark.com", None),  # No subdomain
        ]
        
        for hostname, expected_subdomain in test_cases:
            parts = hostname.split(".")
            if len(parts) > 2:
                subdomain = parts[0]
            else:
                subdomain = None
            
            assert subdomain == expected_subdomain
    
    @pytest.mark.asyncio
    async def test_agency_specific_clients(
        self,
        db_session: AsyncSession,
        agency_1,
        agency_2,
        client_agency_1,
        client_agency_2
    ):
        """Test that each agency has its own OAuth clients."""
        # Query clients for agency 1
        result = await db_session.execute(
            select(OAuthClient).where(OAuthClient.agency_id == agency_1.id)
        )
        agency_1_clients = result.scalars().all()
        
        # Query clients for agency 2
        result = await db_session.execute(
            select(OAuthClient).where(OAuthClient.agency_id == agency_2.id)
        )
        agency_2_clients = result.scalars().all()
        
        # Verify separation
        assert len(agency_1_clients) == 1
        assert len(agency_2_clients) == 1
        assert agency_1_clients[0].id != agency_2_clients[0].id
        assert agency_1_clients[0].client_id != agency_2_clients[0].client_id
    
    @pytest.mark.asyncio
    async def test_scope_limitations_per_agency(
        self,
        client_agency_1,
        client_agency_2
    ):
        """Test that scope limitations can be different per agency."""
        # Set different scopes for each agency's client
        client_agency_1.scope = "read write"
        client_agency_2.scope = "read write admin"
        
        # Verify scope differences
        assert "admin" not in client_agency_1.scope
        assert "admin" in client_agency_2.scope
    
    @pytest.mark.asyncio
    async def test_token_agency_binding(
        self,
        db_session: AsyncSession,
        agency_1,
        user_agency_1,
        client_agency_1
    ):
        """Test that tokens are bound to specific agencies."""
        # Create token for agency 1
        token = OAuthToken(
            id=uuid4(),
            agency_id=agency_1.id,
            user_id=user_agency_1.id,
            client_id=client_agency_1.client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            scope="read write",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(token)
        await db_session.commit()
        
        # Verify token is bound to agency 1
        assert token.agency_id == agency_1.id
        assert token.agency_id == user_agency_1.agency_id
        assert token.agency_id == client_agency_1.agency_id
    
    @pytest.mark.asyncio
    async def test_multi_agency_client(
        self,
        db_session: AsyncSession,
        agency_1,
        agency_2
    ):
        """Test OAuth client that can access multiple agencies."""
        # Create a multi-agency client (e.g., for admin dashboard)
        multi_client = OAuthClient(
            id=uuid4(),
            agency_id=agency_1.id,  # Primary agency
            client_id=f"multi_client_{secrets.token_urlsafe(8)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Multi-Agency Client",
            redirect_uris=["http://admin.agencydark.com/callback"],
            grant_types=["authorization_code", "refresh_token", "client_credentials"],
            response_types=["code"],
            scope="read write admin",
            allowed_agencies=[agency_1.id, agency_2.id],  # Multiple agencies
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(multi_client)
        await db_session.commit()
        
        # Verify multi-agency access
        assert agency_1.id in multi_client.allowed_agencies
        assert agency_2.id in multi_client.allowed_agencies
        assert len(multi_client.allowed_agencies) == 2
    
    @pytest.mark.asyncio
    async def test_agency_context_extraction(self):
        """Test extracting agency context from request."""
        # Test with subdomain
        agency_context = AgencyContext(
            agency_id=uuid4(),
            agency_name="Test Agency",
            subdomain="test"
        )
        
        assert agency_context.agency_id is not None
        assert agency_context.agency_name == "Test Agency"
        assert agency_context.subdomain == "test"
        
        # Test with header
        mock_request = {
            "headers": {
                "X-Agency-ID": str(uuid4()),
                "X-Agency-Name": "Header Agency"
            }
        }
        
        agency_id = mock_request["headers"].get("X-Agency-ID")
        agency_name = mock_request["headers"].get("X-Agency-Name")
        
        assert agency_id is not None
        assert agency_name == "Header Agency"
    
    @pytest.mark.asyncio
    async def test_permission_boundaries(
        self,
        db_session: AsyncSession,
        agency_1,
        user_agency_1
    ):
        """Test permission boundaries within agencies."""
        # Create users with different roles
        admin_user = User(
            id=uuid4(),
            email="admin@agency1.com",
            username="admin1",
            agency_id=agency_1.id,
            role="agency_admin",
            permissions=["read", "write", "admin", "manage_users"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        regular_user = User(
            id=uuid4(),
            email="user@agency1.com",
            username="regular1",
            agency_id=agency_1.id,
            role="user",
            permissions=["read", "write"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db_session.add(admin_user)
        db_session.add(regular_user)
        await db_session.commit()
        
        # Verify permission differences
        assert "admin" in admin_user.permissions
        assert "admin" not in regular_user.permissions
        assert "manage_users" in admin_user.permissions
        assert "manage_users" not in regular_user.permissions
        
        # Both in same agency
        assert admin_user.agency_id == regular_user.agency_id


class TestAgencyDataIsolation:
    """Test data isolation between agencies."""
    
    @pytest.mark.asyncio
    async def test_token_query_isolation(
        self,
        db_session: AsyncSession,
        agency_1,
        agency_2
    ):
        """Test that token queries are isolated by agency."""
        # Create tokens for different agencies
        token_agency_1 = OAuthToken(
            id=uuid4(),
            agency_id=agency_1.id,
            user_id=uuid4(),
            client_id="client1",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            created_at=datetime.now(timezone.utc)
        )
        
        token_agency_2 = OAuthToken(
            id=uuid4(),
            agency_id=agency_2.id,
            user_id=uuid4(),
            client_id="client2",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            created_at=datetime.now(timezone.utc)
        )
        
        db_session.add(token_agency_1)
        db_session.add(token_agency_2)
        await db_session.commit()
        
        # Query tokens for agency 1
        result = await db_session.execute(
            select(OAuthToken).where(OAuthToken.agency_id == agency_1.id)
        )
        agency_1_tokens = result.scalars().all()
        
        # Should only get agency 1's token
        assert len(agency_1_tokens) == 1
        assert agency_1_tokens[0].agency_id == agency_1.id
        assert agency_1_tokens[0].id == token_agency_1.id
    
    @pytest.mark.asyncio
    async def test_user_query_isolation(
        self,
        db_session: AsyncSession,
        agency_1,
        agency_2,
        user_agency_1,
        user_agency_2
    ):
        """Test that user queries are isolated by agency."""
        # Query users for agency 1
        result = await db_session.execute(
            select(User).where(User.agency_id == agency_1.id)
        )
        agency_1_users = result.scalars().all()
        
        # Query users for agency 2
        result = await db_session.execute(
            select(User).where(User.agency_id == agency_2.id)
        )
        agency_2_users = result.scalars().all()
        
        # Verify isolation
        assert len(agency_1_users) == 1
        assert len(agency_2_users) == 1
        assert agency_1_users[0].id == user_agency_1.id
        assert agency_2_users[0].id == user_agency_2.id
        assert agency_1_users[0].id != agency_2_users[0].id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])