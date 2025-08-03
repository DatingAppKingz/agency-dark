#!/usr/bin/env python3
"""Test the minimal auth functionality directly."""
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import asyncpg
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "test-secret-key"

@app.post("/test-login")
async def test_login(email: str, password: str):
    """Direct test login endpoint."""
    try:
        # Connect to database
        conn = await asyncpg.connect("postgresql://mariuszbudzisz@localhost:5432/agencydark")
        
        try:
            # Get user
            user = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.full_name, u.hashed_password, u.role, 
                       u.is_active, u.is_verified, u.agency_id,
                       a.name as agency_name
                FROM users u
                LEFT JOIN agencies a ON u.agency_id = a.id
                WHERE u.email = $1
                """,
                email
            )
            
            if not user:
                return JSONResponse({"error": "User not found"}, status_code=404)
            
            # Verify password
            if not pwd_context.verify(password, user['hashed_password']):
                return JSONResponse({"error": "Invalid password"}, status_code=401)
            
            # Create token
            token_data = {
                "sub": str(user['id']),
                "email": user['email'],
                "exp": datetime.utcnow() + timedelta(minutes=30)
            }
            token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
            
            return {
                "access_token": token,
                "user": {
                    "id": str(user['id']),
                    "email": user['email'],
                    "full_name": user['full_name'],
                    "role": user['role'],
                    "agency_name": user['agency_name']
                }
            }
            
        finally:
            await conn.close()
            
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    print("Starting minimal auth test server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)