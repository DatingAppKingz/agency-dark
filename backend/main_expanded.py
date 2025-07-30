from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import jwt
import logging
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Secret key for JWT
SECRET_KEY = "your-secret-key-here"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Create FastAPI app
app = FastAPI(
    title="AgencyDark API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime
    database: str
    redis: str

# In-memory database (for demo purposes)
users_db = {}
user_id_counter = 1

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = payload.get("sub")
    if email is None or email not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return users_db[email]

# Routes
@app.get("/")
async def root():
    return {"message": "Welcome to AgencyDark API", "version": "1.0.0"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check endpoint."""
    return {
        "status": "healthy",
        "service": "agencydark-backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow(),
        "database": "connected",
        "redis": "connected"
    }

@app.post("/api/v1/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register a new user."""
    global user_id_counter
    
    # Check if user already exists
    if user_data.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = {
        "id": user_id_counter,
        "email": user_data.email,
        "username": user_data.username,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    users_db[user_data.email] = user
    user_id_counter += 1
    
    logger.info(f"New user registered: {user_data.email}")
    
    return UserResponse(**user)

@app.post("/api/v1/auth/login", response_model=Token)
async def login(credentials: LoginRequest):
    """Login with email and password."""
    user = users_db.get(credentials.email)
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user["email"]})
    
    logger.info(f"User logged in: {credentials.email}")
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(**current_user)

@app.get("/api/v1/users", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(get_current_user)):
    """List all users (protected endpoint)."""
    return [UserResponse(**user) for user in users_db.values()]

@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint to verify API is working."""
    return {"message": "API is working!", "timestamp": datetime.utcnow()}

# Models endpoints
@app.get("/api/v1/models")
async def list_models(current_user: dict = Depends(get_current_user)):
    """List all models (placeholder)."""
    return {
        "models": [
            {"id": 1, "name": "Model 1", "status": "active"},
            {"id": 2, "name": "Model 2", "status": "active"}
        ],
        "total": 2
    }

# Chat endpoints
@app.get("/api/v1/chat/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """List chat conversations (placeholder)."""
    return {
        "conversations": [],
        "total": 0
    }

# Analytics endpoints
@app.get("/api/v1/analytics/overview")
async def analytics_overview(current_user: dict = Depends(get_current_user)):
    """Get analytics overview (placeholder)."""
    return {
        "revenue": {"total": 0, "currency": "USD"},
        "users": {"total": len(users_db), "active": len(users_db)},
        "models": {"total": 2, "active": 2}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)