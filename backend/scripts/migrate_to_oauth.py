#!/usr/bin/env python3
"""
Migration script to convert existing JWT authentication to OAuth2.0.
Handles user sessions, API keys, and client creation.
"""
import asyncio
import argparse
import logging
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID, uuid4
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete
import redis.asyncio as redis

from oauth.models import OAuthClient, OAuthToken, OAuthAuthorizationCode
from oauth.provider import create_authorization_server
from models.user import User
from models.agency import Agency
from core.database import Base
from core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OAuthMigration:
    """
    Handles migration from JWT to OAuth2.0.
    """
    
    def __init__(
        self,
        database_url: str,
        redis_url: str,
        dry_run: bool = False,
        batch_size: int = 100
    ):
        """
        Initialize migration handler.
        
        Args:
            database_url: Database connection URL
            redis_url: Redis connection URL
            dry_run: If True, don't commit changes
            batch_size: Number of records to process at once
        """
        self.database_url = database_url
        self.redis_url = redis_url
        self.dry_run = dry_run
        self.batch_size = batch_size
        
        # Track migration statistics
        self.stats = {
            "users_processed": 0,
            "clients_created": 0,
            "tokens_created": 0,
            "sessions_migrated": 0,
            "api_keys_migrated": 0,
            "errors": 0
        }
        
        # Initialize connections
        self.engine = None
        self.session_factory = None
        self.redis_client = None
    
    async def initialize(self):
        """
        Initialize database and Redis connections.
        """
        logger.info("Initializing connections...")
        
        # Create async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True
        )
        
        # Create session factory
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Initialize Redis
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )
        
        logger.info("Connections initialized")
    
    async def cleanup(self):
        """
        Clean up connections.
        """
        if self.redis_client:
            await self.redis_client.close()
        
        if self.engine:
            await self.engine.dispose()
    
    async def create_agency_oauth_clients(self, session: AsyncSession) -> Dict[UUID, OAuthClient]:
        """
        Create OAuth clients for each agency.
        
        Returns:
            Dictionary mapping agency ID to OAuth client
        """
        logger.info("Creating OAuth clients for agencies...")
        
        # Get all agencies
        result = await session.execute(select(Agency))
        agencies = result.scalars().all()
        
        agency_clients = {}
        
        for agency in agencies:
            # Check if client already exists
            existing = await session.execute(
                select(OAuthClient).where(
                    OAuthClient.agency_id == agency.id,
                    OAuthClient.client_name == f"{agency.name} Default Client"
                )
            )
            client = existing.scalar_one_or_none()
            
            if not client:
                # Create new OAuth client for agency
                client = OAuthClient(
                    id=uuid4(),
                    agency_id=agency.id,
                    client_id=f"agency_{agency.id}_{secrets.token_urlsafe(16)}",
                    client_secret=secrets.token_urlsafe(32),
                    client_name=f"{agency.name} Default Client",
                    redirect_uris=[
                        f"https://{agency.subdomain}.agencydark.com/callback",
                        "http://localhost:3000/callback"  # Development
                    ],
                    grant_types=["authorization_code", "refresh_token", "password"],
                    response_types=["code"],
                    scope="read write admin",
                    allowed_agencies=[agency.id],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                session.add(client)
                self.stats["clients_created"] += 1
                logger.info(f"Created OAuth client for agency: {agency.name}")
            
            agency_clients[agency.id] = client
        
        if not self.dry_run:
            await session.commit()
        
        return agency_clients
    
    async def migrate_user_sessions(
        self,
        session: AsyncSession,
        agency_clients: Dict[UUID, OAuthClient]
    ):
        """
        Migrate existing user sessions to OAuth tokens.
        """
        logger.info("Migrating user sessions...")
        
        # Get all session keys from Redis
        cursor = 0
        pattern = "session:*"
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor,
                match=pattern,
                count=self.batch_size
            )
            
            for key in keys:
                try:
                    # Get session data
                    session_data = await self.redis_client.hgetall(key)
                    
                    if not session_data:
                        continue
                    
                    user_id = session_data.get("user_id")
                    agency_id = session_data.get("agency_id")
                    
                    if not user_id or not agency_id:
                        continue
                    
                    # Get OAuth client for agency
                    client = agency_clients.get(UUID(agency_id))
                    if not client:
                        logger.warning(f"No OAuth client for agency {agency_id}")
                        continue
                    
                    # Check if token already exists
                    existing = await session.execute(
                        select(OAuthToken).where(
                            OAuthToken.user_id == UUID(user_id),
                            OAuthToken.client_id == client.client_id
                        )
                    )
                    
                    if not existing.scalar_one_or_none():
                        # Create OAuth token
                        token = OAuthToken(
                            id=uuid4(),
                            agency_id=UUID(agency_id),
                            user_id=UUID(user_id),
                            client_id=client.client_id,
                            token_type="Bearer",
                            access_token=secrets.token_urlsafe(32),
                            refresh_token=secrets.token_urlsafe(32),
                            scope="read write",
                            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                            extra_data={
                                "migrated_from": "session",
                                "session_key": key,
                                "migrated_at": datetime.now(timezone.utc).isoformat()
                            },
                            created_at=datetime.now(timezone.utc)
                        )
                        
                        session.add(token)
                        self.stats["tokens_created"] += 1
                        
                        # Update Redis session with OAuth token
                        await self.redis_client.hset(
                            key,
                            mapping={
                                "oauth_token": token.access_token,
                                "oauth_client_id": client.client_id
                            }
                        )
                        
                        self.stats["sessions_migrated"] += 1
                        logger.debug(f"Migrated session for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error migrating session {key}: {e}")
                    self.stats["errors"] += 1
            
            # Check if we're done
            if cursor == 0:
                break
        
        if not self.dry_run:
            await session.commit()
    
    async def migrate_api_keys(
        self,
        session: AsyncSession,
        agency_clients: Dict[UUID, OAuthClient]
    ):
        """
        Convert existing API keys to OAuth clients.
        """
        logger.info("Migrating API keys...")
        
        # Note: This assumes you have an APIKey model
        # Adjust based on your actual implementation
        
        # For demonstration, we'll create service clients for known API keys
        # In production, you'd query your actual API keys table
        
        # Example: Create a service client for each agency's API access
        for agency_id, agency_client in agency_clients.items():
            # Create a service account client
            service_client = await session.execute(
                select(OAuthClient).where(
                    OAuthClient.agency_id == agency_id,
                    OAuthClient.client_name.like("%Service Account%")
                )
            )
            
            if not service_client.scalar_one_or_none():
                client = OAuthClient(
                    id=uuid4(),
                    agency_id=agency_id,
                    client_id=f"service_{agency_id}_{secrets.token_urlsafe(16)}",
                    client_secret=secrets.token_urlsafe(32),
                    client_name=f"Service Account - Agency {agency_id}",
                    redirect_uris=[],  # No redirects for service accounts
                    grant_types=["client_credentials"],
                    response_types=[],
                    scope="read write api",
                    allowed_agencies=[agency_id],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                session.add(client)
                self.stats["api_keys_migrated"] += 1
                logger.info(f"Created service account for agency {agency_id}")
        
        if not self.dry_run:
            await session.commit()
    
    async def migrate_user_data(self, session: AsyncSession):
        """
        Update user records for OAuth compatibility.
        """
        logger.info("Updating user records...")
        
        # Process users in batches
        offset = 0
        
        while True:
            # Get batch of users
            result = await session.execute(
                select(User)
                .offset(offset)
                .limit(self.batch_size)
            )
            users = result.scalars().all()
            
            if not users:
                break
            
            for user in users:
                try:
                    # Add OAuth metadata if not present
                    if not user.oauth_metadata:
                        user.oauth_metadata = {
                            "migrated": True,
                            "migration_date": datetime.now(timezone.utc).isoformat(),
                            "original_auth": "jwt"
                        }
                    
                    # Ensure user has required OAuth fields
                    if not hasattr(user, 'oauth_provider'):
                        user.oauth_provider = None
                    
                    if not hasattr(user, 'oauth_id'):
                        user.oauth_id = None
                    
                    self.stats["users_processed"] += 1
                    
                except Exception as e:
                    logger.error(f"Error updating user {user.id}: {e}")
                    self.stats["errors"] += 1
            
            offset += self.batch_size
        
        if not self.dry_run:
            await session.commit()
    
    async def validate_migration(self, session: AsyncSession) -> bool:
        """
        Validate the migration was successful.
        
        Returns:
            True if validation passes
        """
        logger.info("Validating migration...")
        
        # Check OAuth clients exist
        client_count = await session.execute(
            select(OAuthClient).count()
        )
        if client_count.scalar() == 0:
            logger.error("No OAuth clients found")
            return False
        
        # Check tokens were created
        token_count = await session.execute(
            select(OAuthToken).count()
        )
        logger.info(f"Found {token_count.scalar()} OAuth tokens")
        
        # Check Redis sessions have OAuth info
        sample_keys = await self.redis_client.keys("session:*")
        if sample_keys:
            sample_session = await self.redis_client.hgetall(sample_keys[0])
            if "oauth_token" not in sample_session and self.stats["sessions_migrated"] > 0:
                logger.warning("Sample session missing OAuth token")
        
        return True
    
    async def generate_report(self) -> str:
        """
        Generate migration report.
        
        Returns:
            Report string
        """
        report = [
            "=" * 60,
            "OAuth Migration Report",
            "=" * 60,
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Dry Run: {self.dry_run}",
            "",
            "Statistics:",
            f"  Users Processed: {self.stats['users_processed']}",
            f"  OAuth Clients Created: {self.stats['clients_created']}",
            f"  OAuth Tokens Created: {self.stats['tokens_created']}",
            f"  Sessions Migrated: {self.stats['sessions_migrated']}",
            f"  API Keys Migrated: {self.stats['api_keys_migrated']}",
            f"  Errors: {self.stats['errors']}",
            "",
        ]
        
        if self.stats['errors'] > 0:
            report.append("⚠️  Migration completed with errors. Review logs for details.")
        elif self.dry_run:
            report.append("✅ Dry run completed successfully. Run without --dry-run to apply changes.")
        else:
            report.append("✅ Migration completed successfully!")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    async def run(self):
        """
        Execute the migration.
        """
        try:
            await self.initialize()
            
            async with self.session_factory() as session:
                # Create OAuth clients for agencies
                agency_clients = await self.create_agency_oauth_clients(session)
                
                # Migrate user sessions
                await self.migrate_user_sessions(session, agency_clients)
                
                # Migrate API keys
                await self.migrate_api_keys(session, agency_clients)
                
                # Update user data
                await self.migrate_user_data(session)
                
                # Validate migration
                if not self.dry_run:
                    valid = await self.validate_migration(session)
                    if not valid:
                        logger.error("Migration validation failed")
                        self.stats["errors"] += 1
            
            # Generate and print report
            report = await self.generate_report()
            print(report)
            
            # Save report to file
            report_path = Path("migration_report.txt")
            report_path.write_text(report)
            logger.info(f"Report saved to {report_path}")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.cleanup()


async def main():
    """
    Main entry point for migration script.
    """
    parser = argparse.ArgumentParser(
        description="Migrate from JWT to OAuth2.0 authentication"
    )
    
    parser.add_argument(
        "--database-url",
        default=settings.DATABASE_URL,
        help="Database connection URL"
    )
    
    parser.add_argument(
        "--redis-url",
        default=settings.REDIS_URL,
        help="Redis connection URL"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without committing changes"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process at once"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run migration
    migration = OAuthMigration(
        database_url=args.database_url,
        redis_url=args.redis_url,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
    
    await migration.run()


if __name__ == "__main__":
    asyncio.run(main())