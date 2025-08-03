"""Simple auth test endpoint that works with actual database schema."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
import psycopg2
import jwt
from datetime import datetime, timedelta

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class LoginRequest(BaseModel):
    email: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/api/v1/auth/login")
async def login(request: LoginRequest):
    # Connect to database
    conn = psycopg2.connect('postgresql://mariuszbudzisz@localhost/agencydark_dev')
    cur = conn.cursor()
    
    # Get user by email with all needed fields in one query
    cur.execute(
        "SELECT id, email, hashed_password, full_name, role, is_active, agency_id, created_at, verified_at FROM users WHERE email = %s",
        (request.email,)
    )
    user = cur.fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user_id, email, hashed_password, full_name, role, is_active, agency_id, created_at, verified_at = user
    
    # Check if user is active
    if not is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    # Verify password
    if not pwd_context.verify(request.password, hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    conn.close()
    
    # Create token
    access_token = create_access_token({"sub": str(user_id), "email": email})
    
    # Format dates properly
    created_at_str = created_at.isoformat() + "Z" if created_at else datetime.utcnow().isoformat() + "Z"
    verified_at_str = verified_at.isoformat() + "Z" if verified_at else None
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user_id),
            "email": email,
            "full_name": full_name,
            "role": role.lower() if role else "agency_member",  # Convert to lowercase
            "agency_id": str(agency_id) if agency_id else None,
            "is_active": is_active,
            "created_at": created_at_str,
            "verified_at": verified_at_str
        }
    }

@app.get("/api/v1/auth/me")
async def get_current_user():
    """Get current user endpoint."""
    # For now, return the admin user info
    # In a real app, you'd decode the JWT token from the Authorization header
    return {
        "id": "c2aadc72-7020-447c-bf9a-241a94f4bc08",
        "email": "admin@agency.com",
        "full_name": "Admin User",
        "role": "super_admin",
        "agency_id": None,
        "is_active": True,
        "created_at": "2025-08-03T16:16:31.453927Z",
        "verified_at": None
    }

@app.get("/")
def root():
    return {"message": "Auth test server running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)