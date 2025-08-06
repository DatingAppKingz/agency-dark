"""
Simple main.py with fixed authentication
Using plain text password comparison
"""
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import uvicorn
import os
from pydantic import BaseModel
from typing import Optional

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")

# Request/Response models
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

# Simple JWT token creation (just for testing)
def create_simple_token(user_email: str) -> str:
    import json
    import base64
    # Simple token - just base64 encoded user email
    token_data = {"email": user_email}
    return base64.b64encode(json.dumps(token_data).encode()).decode()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up Simple AgencyDark API...")
    yield
    # Shutdown
    print("Shutting down Simple AgencyDark API...")

# Create app
app = FastAPI(
    title="AgencyDark API (Simple)",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AgencyDark API (Simple) - Authentication Fixed"}

@app.get("/health")
async def health():
    return {"status": "healthy", "auth": "plain_text"}

@app.post("/api/v1/auth/login")
async def login(request: LoginRequest):
    """
    Simple login with plain text password comparison
    """
    # Direct database connection
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Get user from database
        row = await conn.fetchrow(
            "SELECT id, email, hashed_password, role FROM users WHERE email = $1",
            request.email
        )
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Plain text password comparison
        print(f"Comparing: '{request.password}' with '{row['hashed_password']}'")
        if request.password != row['hashed_password']:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Login successful - create token
        token = create_simple_token(row['email'])
        
        return TokenResponse(
            access_token=token,
            user={
                "id": str(row['id']),
                "email": row['email'],
                "role": row['role'] or "user"
            }
        )
    finally:
        await conn.close()

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Get current user from token (simplified)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        import json
        import base64
        token_data = json.loads(base64.b64decode(token))
        return {"email": token_data["email"], "authenticated": True}
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
