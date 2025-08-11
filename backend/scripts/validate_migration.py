#!/usr/bin/env python3
"""
Validation script to verify OAuth migration was successful.
Performs comprehensive checks on migrated data.
"""
import asyncio
import argparse
import logging
import sys
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
import redis.asyncio as redis

from oauth.models import OAuthClient, OAuthToken, OAuthAuthorizationCode
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


class MigrationValidator:
    """
    Validates OAuth migration results.
    """
    
    def __init__(
        self,
        database_url: str,
        redis_url: str,
        detailed: bool = False
    ):
        """
        Initialize validator.
        
        Args:
            database_url: Database connection URL
            redis_url: Redis connection URL
            detailed: Show detailed validation results
        """
        self.database_url = database_url
        self.redis_url = redis_url
        self.detailed = detailed
        
        # Track validation results
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
        
        # Initialize connections
        self.engine = None
        self.session_factory = None
        self.redis_client = None
    
    async def initialize(self):
        """
        Initialize database and Redis connections.
        """
        logger.info("Initializing connections for validation...")
        
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
    
    def add_result(self, category: str, test_name: str, message: str):
        """
        Add a validation result.
        
        Args:
            category: passed, failed, or warnings
            test_name: Name of the test
            message: Result message
        """
        self.results[category].append({
            "test": test_name,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if category == "passed":
            logger.info(f"✅ {test_name}: {message}")
        elif category == "failed":
            logger.error(f"❌ {test_name}: {message}")
        else:
            logger.warning(f"⚠️  {test_name}: {message}")
    
    async def validate_oauth_clients(self, session: AsyncSession) -> bool:
        """
        Validate OAuth clients are properly created.
        
        Returns:
            True if validation passes
        """
        test_name = "OAuth Clients"
        
        try:
            # Count total agencies
            agency_count = await session.execute(
                select(func.count()).select_from(Agency)
            )
            total_agencies = agency_count.scalar()
            
            # Count OAuth clients
            client_count = await session.execute(
                select(func.count()).select_from(OAuthClient)
            )
            total_clients = client_count.scalar()
            
            if total_clients == 0:
                self.add_result("failed", test_name, "No OAuth clients found")
                return False
            
            # Check each agency has at least one client
            agencies_without_clients = await session.execute(
                select(Agency).where(
                    ~Agency.id.in_(
                        select(OAuthClient.agency_id).distinct()
                    )
                )
            )
            
            missing_agencies = agencies_without_clients.scalars().all()
            
            if missing_agencies:
                for agency in missing_agencies:
                    self.add_result(
                        "warnings",
                        test_name,
                        f"Agency '{agency.name}' has no OAuth client"
                    )
            
            # Validate client configurations
            clients = await session.execute(select(OAuthClient))
            
            for client in clients.scalars():
                # Check required fields
                if not client.client_id or not client.client_secret:
                    self.add_result(
                        "failed",
                        test_name,
                        f"Client {client.id} missing credentials"
                    )
                    return False
                
                # Check grant types
                if not client.grant_types:
                    self.add_result(
                        "warnings",
                        test_name,
                        f"Client {client.client_name} has no grant types"
                    )
                
                # Check redirect URIs for auth code grant
                if "authorization_code" in (client.grant_types or []):
                    if not client.redirect_uris:
                        self.add_result(
                            "warnings",
                            test_name,
                            f"Client {client.client_name} uses auth code but has no redirect URIs"
                        )
            
            self.add_result(
                "passed",
                test_name,
                f"Found {total_clients} OAuth clients for {total_agencies} agencies"
            )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def validate_oauth_tokens(self, session: AsyncSession) -> bool:
        """
        Validate OAuth tokens are properly created.
        
        Returns:
            True if validation passes
        """
        test_name = "OAuth Tokens"
        
        try:
            # Count total tokens
            token_count = await session.execute(
                select(func.count()).select_from(OAuthToken)
            )
            total_tokens = token_count.scalar()
            
            if total_tokens == 0:
                self.add_result("warnings", test_name, "No OAuth tokens found (may be normal if no active sessions)")
                return True
            
            # Check token validity
            invalid_tokens = await session.execute(
                select(OAuthToken).where(
                    (OAuthToken.access_token == None) |
                    (OAuthToken.token_type != "Bearer")
                )
            )
            
            invalid = invalid_tokens.scalars().all()
            if invalid:
                self.add_result(
                    "failed",
                    test_name,
                    f"Found {len(invalid)} invalid tokens"
                )
                return False
            
            # Check expired tokens
            now = datetime.now(timezone.utc)
            expired_count = await session.execute(
                select(func.count()).select_from(OAuthToken).where(
                    OAuthToken.expires_at < now
                )
            )
            expired = expired_count.scalar()
            
            if expired > 0:
                self.add_result(
                    "warnings",
                    test_name,
                    f"Found {expired} expired tokens"
                )
            
            # Check tokens have valid clients
            orphaned_tokens = await session.execute(
                select(OAuthToken).where(
                    ~OAuthToken.client_id.in_(
                        select(OAuthClient.client_id)
                    )
                )
            )
            
            orphaned = orphaned_tokens.scalars().all()
            if orphaned:
                self.add_result(
                    "failed",
                    test_name,
                    f"Found {len(orphaned)} tokens with invalid client_id"
                )
                return False
            
            self.add_result(
                "passed",
                test_name,
                f"Validated {total_tokens} OAuth tokens"
            )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def validate_user_migration(self, session: AsyncSession) -> bool:
        """
        Validate user records are properly updated.
        
        Returns:
            True if validation passes
        """
        test_name = "User Migration"
        
        try:
            # Count total users
            user_count = await session.execute(
                select(func.count()).select_from(User)
            )
            total_users = user_count.scalar()
            
            # Check users with OAuth metadata
            migrated_count = await session.execute(
                select(func.count()).select_from(User).where(
                    User.oauth_metadata != None
                )
            )
            migrated = migrated_count.scalar()
            
            if self.detailed:
                # Check individual user fields
                users = await session.execute(select(User).limit(100))
                
                for user in users.scalars():
                    if user.oauth_metadata:
                        metadata = user.oauth_metadata
                        if not metadata.get("migrated"):
                            self.add_result(
                                "warnings",
                                test_name,
                                f"User {user.id} has incomplete OAuth metadata"
                            )
            
            migration_rate = (migrated / total_users * 100) if total_users > 0 else 0
            
            self.add_result(
                "passed",
                test_name,
                f"Migrated {migrated}/{total_users} users ({migration_rate:.1f}%)"
            )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def validate_redis_sessions(self) -> bool:
        """
        Validate Redis sessions have OAuth information.
        
        Returns:
            True if validation passes
        """
        test_name = "Redis Sessions"
        
        try:
            # Get sample of session keys
            session_keys = []
            cursor = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match="session:*",
                    count=10
                )
                session_keys.extend(keys)
                
                if cursor == 0 or len(session_keys) >= 100:
                    break
            
            if not session_keys:
                self.add_result(
                    "warnings",
                    test_name,
                    "No active sessions found in Redis"
                )
                return True
            
            # Check sessions for OAuth data
            sessions_with_oauth = 0
            sessions_without_oauth = 0
            
            for key in session_keys[:100]:  # Check up to 100 sessions
                session_data = await self.redis_client.hgetall(key)
                
                if session_data:
                    if "oauth_token" in session_data or "oauth_client_id" in session_data:
                        sessions_with_oauth += 1
                    else:
                        sessions_without_oauth += 1
            
            if sessions_without_oauth > 0:
                self.add_result(
                    "warnings",
                    test_name,
                    f"Found {sessions_without_oauth} sessions without OAuth data"
                )
            
            self.add_result(
                "passed",
                test_name,
                f"Checked {len(session_keys)} sessions, {sessions_with_oauth} have OAuth data"
            )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def validate_authentication_flow(self, session: AsyncSession) -> bool:
        """
        Test that authentication flow works with OAuth.
        
        Returns:
            True if validation passes
        """
        test_name = "Authentication Flow"
        
        try:
            # Get a test client
            test_client = await session.execute(
                select(OAuthClient).limit(1)
            )
            client = test_client.scalar_one_or_none()
            
            if not client:
                self.add_result(
                    "failed",
                    test_name,
                    "No OAuth client available for testing"
                )
                return False
            
            # Check client has proper configuration
            checks = [
                (bool(client.client_id), "Client ID exists"),
                (bool(client.client_secret), "Client secret exists"),
                (bool(client.grant_types), "Grant types configured"),
                ("authorization_code" in (client.grant_types or []), "Authorization code grant enabled"),
                (bool(client.redirect_uris), "Redirect URIs configured"),
            ]
            
            all_passed = True
            for check, description in checks:
                if not check:
                    self.add_result(
                        "warnings",
                        test_name,
                        f"Test client missing: {description}"
                    )
                    all_passed = False
            
            if all_passed:
                self.add_result(
                    "passed",
                    test_name,
                    "OAuth authentication flow configuration valid"
                )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def validate_permissions(self, session: AsyncSession) -> bool:
        """
        Validate OAuth scopes and permissions are properly set.
        
        Returns:
            True if validation passes
        """
        test_name = "Permissions & Scopes"
        
        try:
            # Check OAuth clients have scopes
            clients_without_scope = await session.execute(
                select(OAuthClient).where(
                    (OAuthClient.scope == None) |
                    (OAuthClient.scope == "")
                )
            )
            
            no_scope = clients_without_scope.scalars().all()
            if no_scope:
                for client in no_scope:
                    self.add_result(
                        "warnings",
                        test_name,
                        f"Client {client.client_name} has no scopes defined"
                    )
            
            # Check tokens have valid scopes
            tokens = await session.execute(
                select(OAuthToken).limit(100)
            )
            
            invalid_scope_count = 0
            for token in tokens.scalars():
                if not token.scope:
                    invalid_scope_count += 1
            
            if invalid_scope_count > 0:
                self.add_result(
                    "warnings",
                    test_name,
                    f"Found {invalid_scope_count} tokens without scopes"
                )
            
            self.add_result(
                "passed",
                test_name,
                "Permission and scope validation complete"
            )
            
            return True
            
        except Exception as e:
            self.add_result("failed", test_name, f"Validation error: {e}")
            return False
    
    async def generate_report(self) -> str:
        """
        Generate validation report.
        
        Returns:
            Report string
        """
        report = [
            "=" * 60,
            "OAuth Migration Validation Report",
            "=" * 60,
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Detailed Mode: {self.detailed}",
            "",
        ]
        
        # Summary
        total_tests = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["warnings"])
        report.extend([
            "Summary:",
            f"  Total Tests: {total_tests}",
            f"  Passed: {len(self.results['passed'])}",
            f"  Failed: {len(self.results['failed'])}",
            f"  Warnings: {len(self.results['warnings'])}",
            "",
        ])
        
        # Passed tests
        if self.results["passed"]:
            report.append("✅ Passed Tests:")
            for result in self.results["passed"]:
                report.append(f"  - {result['test']}: {result['message']}")
            report.append("")
        
        # Warnings
        if self.results["warnings"]:
            report.append("⚠️  Warnings:")
            for result in self.results["warnings"]:
                report.append(f"  - {result['test']}: {result['message']}")
            report.append("")
        
        # Failed tests
        if self.results["failed"]:
            report.append("❌ Failed Tests:")
            for result in self.results["failed"]:
                report.append(f"  - {result['test']}: {result['message']}")
            report.append("")
        
        # Overall result
        if self.results["failed"]:
            report.append("❌ VALIDATION FAILED - Migration has critical issues")
        elif self.results["warnings"]:
            report.append("⚠️  VALIDATION PASSED WITH WARNINGS - Review warnings above")
        else:
            report.append("✅ VALIDATION PASSED - Migration successful!")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    async def run(self):
        """
        Execute validation.
        """
        try:
            await self.initialize()
            
            async with self.session_factory() as session:
                # Run validation tests
                await self.validate_oauth_clients(session)
                await self.validate_oauth_tokens(session)
                await self.validate_user_migration(session)
                await self.validate_redis_sessions()
                await self.validate_authentication_flow(session)
                await self.validate_permissions(session)
            
            # Generate and print report
            report = await self.generate_report()
            print(report)
            
            # Save report to file
            report_path = Path("validation_report.txt")
            report_path.write_text(report)
            logger.info(f"Report saved to {report_path}")
            
            # Return exit code based on results
            return 0 if not self.results["failed"] else 1
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return 1
        finally:
            await self.cleanup()


async def main():
    """
    Main entry point for validation script.
    """
    parser = argparse.ArgumentParser(
        description="Validate OAuth migration results"
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
        "--detailed",
        action="store_true",
        help="Show detailed validation results"
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
    
    # Run validation
    validator = MigrationValidator(
        database_url=args.database_url,
        redis_url=args.redis_url,
        detailed=args.detailed
    )
    
    exit_code = await validator.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())