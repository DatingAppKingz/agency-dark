"""
Test authentication directly with minimal dependencies.
"""
import asyncio
from sqlalchemy import text
from core.database import engine
from core.security_v2 import verify_password, create_token_pair

async def test_login():
    """Test login directly."""
    async with engine.begin() as conn:
        # Get user directly
        result = await conn.execute(
            text("""
                SELECT id, email, hashed_password, role, is_active, agency_id
                FROM users 
                WHERE email = :email
            """),
            {"email": "admin@agency.com"}
        )
        user = result.fetchone()
        
        if user:
            user_id, email, password_hash, role, is_active, agency_id = user
            print(f"User found: {email}")
            print(f"Role: {role}")
            print(f"Active: {is_active}")
            
            # Test password
            is_valid = verify_password("admin123", password_hash)
            print(f"Password valid: {is_valid}")
            
            if is_valid and is_active:
                # Create tokens
                access_token, refresh_token = create_token_pair(
                    user_id=str(user_id),
                    email=email,
                    role=role,
                    additional_claims={
                        "agency_id": str(agency_id) if agency_id else None
                    }
                )
                
                print(f"\n✅ Login successful!")
                print(f"Access token: {access_token[:50]}...")
                print(f"Refresh token: {refresh_token[:50]}...")
                
                # Update last login
                await conn.execute(
                    text("UPDATE users SET last_login = NOW() WHERE id = :id"),
                    {"id": user_id}
                )
                print("Last login updated")
        else:
            print("User not found")

asyncio.run(test_login())