"""
Data migration script for transitioning to security_v2.
Migrates users, passwords, and permissions to new format.
"""
import asyncio
import logging
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..authentication import hash_password
from .permission_mapper import map_old_role_to_new

logger = logging.getLogger(__name__)

class DataMigrator:
    """Handles data migration to new security system."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize data migrator.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.migration_stats = {
            'users_processed': 0,
            'passwords_hashed': 0,
            'roles_migrated': 0,
            'errors': []
        }
    
    async def migrate_all(self) -> Dict[str, Any]:
        """
        Run all migrations.
        
        Returns:
            Migration statistics
        """
        logger.info("Starting security data migration...")
        
        # Migrate user passwords
        await self.migrate_passwords()
        
        # Migrate user roles
        await self.migrate_roles()
        
        logger.info(f"Migration complete: {self.migration_stats}")
        return self.migration_stats
    
    async def migrate_passwords(self) -> None:
        """Migrate plain text passwords to hashed passwords."""
        logger.info("Migrating user passwords...")
        
        try:
            # Get all users
            result = await self.db.execute(
                text("SELECT id, email, hashed_password FROM users")
            )
            users = result.fetchall()
            
            for user in users:
                user_id, email, current_password = user
                self.migration_stats['users_processed'] += 1
                
                # Check if password needs hashing
                if current_password and not current_password.startswith('$2b$'):
                    # This is a plain text password, hash it
                    try:
                        hashed = hash_password(current_password)
                        
                        # Update in database
                        await self.db.execute(
                            text(
                                "UPDATE users SET hashed_password = :password WHERE id = :id"
                            ),
                            {"password": hashed, "id": user_id}
                        )
                        
                        self.migration_stats['passwords_hashed'] += 1
                        logger.info(f"Hashed password for user {email}")
                        
                    except Exception as e:
                        error_msg = f"Failed to hash password for user {email}: {e}"
                        logger.error(error_msg)
                        self.migration_stats['errors'].append(error_msg)
            
            # Commit changes
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Password migration failed: {e}")
            self.migration_stats['errors'].append(f"Password migration error: {e}")
            await self.db.rollback()
    
    async def migrate_roles(self) -> None:
        """Migrate old role names to new Role enum values."""
        logger.info("Migrating user roles...")
        
        try:
            # Get all users with roles
            result = await self.db.execute(
                text("SELECT id, email, role FROM users WHERE role IS NOT NULL")
            )
            users = result.fetchall()
            
            for user in users:
                user_id, email, old_role = user
                
                # Map to new role
                new_role = map_old_role_to_new(old_role)
                
                # Only update if role changed
                if new_role != old_role:
                    try:
                        await self.db.execute(
                            text(
                                "UPDATE users SET role = :role WHERE id = :id"
                            ),
                            {"role": new_role, "id": user_id}
                        )
                        
                        self.migration_stats['roles_migrated'] += 1
                        logger.info(f"Migrated role for user {email}: {old_role} -> {new_role}")
                        
                    except Exception as e:
                        error_msg = f"Failed to migrate role for user {email}: {e}"
                        logger.error(error_msg)
                        self.migration_stats['errors'].append(error_msg)
            
            # Commit changes
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Role migration failed: {e}")
            self.migration_stats['errors'].append(f"Role migration error: {e}")
            await self.db.rollback()
    
    async def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that migration was successful.
        
        Returns:
            Verification results
        """
        logger.info("Verifying migration...")
        
        verification = {
            'total_users': 0,
            'hashed_passwords': 0,
            'plain_passwords': 0,
            'valid_roles': 0,
            'invalid_roles': 0,
            'issues': []
        }
        
        try:
            # Check passwords
            result = await self.db.execute(
                text("SELECT COUNT(*) FROM users")
            )
            verification['total_users'] = result.scalar()
            
            result = await self.db.execute(
                text("SELECT COUNT(*) FROM users WHERE hashed_password LIKE '$2b$%'")
            )
            verification['hashed_passwords'] = result.scalar()
            
            result = await self.db.execute(
                text(
                    "SELECT COUNT(*) FROM users "
                    "WHERE hashed_password IS NOT NULL "
                    "AND hashed_password NOT LIKE '$2b$%'"
                )
            )
            verification['plain_passwords'] = result.scalar()
            
            if verification['plain_passwords'] > 0:
                verification['issues'].append(
                    f"{verification['plain_passwords']} users still have plain text passwords"
                )
            
            # Check roles
            valid_roles = [
                'super_admin', 'agency_owner', 'agency_admin',
                'agency_user', 'model', 'client', 'viewer'
            ]
            
            result = await self.db.execute(
                text(
                    "SELECT COUNT(*) FROM users WHERE role IN :roles"
                ),
                {"roles": tuple(valid_roles)}
            )
            verification['valid_roles'] = result.scalar()
            
            result = await self.db.execute(
                text(
                    "SELECT COUNT(*) FROM users "
                    "WHERE role IS NOT NULL AND role NOT IN :roles"
                ),
                {"roles": tuple(valid_roles)}
            )
            verification['invalid_roles'] = result.scalar()
            
            if verification['invalid_roles'] > 0:
                verification['issues'].append(
                    f"{verification['invalid_roles']} users have invalid roles"
                )
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            verification['issues'].append(f"Verification error: {e}")
        
        return verification


async def run_migration(db_session: AsyncSession) -> Dict[str, Any]:
    """
    Run the security data migration.
    
    Args:
        db_session: Database session
        
    Returns:
        Migration results
    """
    migrator = DataMigrator(db_session)
    
    # Run migration
    stats = await migrator.migrate_all()
    
    # Verify migration
    verification = await migrator.verify_migration()
    
    return {
        'migration_stats': stats,
        'verification': verification
    }


# Standalone migration script
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    from core.database import get_db_session
    
    async def main():
        """Run migration as standalone script."""
        logging.basicConfig(level=logging.INFO)
        
        async with get_db_session() as session:
            results = await run_migration(session)
            
            print("\n" + "=" * 50)
            print("MIGRATION RESULTS")
            print("=" * 50)
            print(f"\nMigration Stats:")
            for key, value in results['migration_stats'].items():
                print(f"  {key}: {value}")
            
            print(f"\nVerification:")
            for key, value in results['verification'].items():
                print(f"  {key}: {value}")
            
            if results['verification']['issues']:
                print("\n⚠️  Issues found:")
                for issue in results['verification']['issues']:
                    print(f"  - {issue}")
            else:
                print("\n✅ Migration completed successfully!")
    
    asyncio.run(main())