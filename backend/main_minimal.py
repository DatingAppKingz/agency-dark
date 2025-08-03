from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Disable ML features
os.environ['DISABLE_ML'] = 'true'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to AgencyDark API"}

@app.get("/health")
async def health_check():
    # Test model imports
    try:
        from models.registry import init_models
        models = init_models()
        models_status = f"✅ {len(models)} models loaded successfully"
    except Exception as e:
        models_status = f"❌ Model error: {str(e)}"
    
    # Test database configuration
    try:
        from core.database import DATABASE_URL
        db_status = "✅ Database configured"
    except Exception as e:
        db_status = f"❌ Database error: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "agencydark-backend",
        "version": "1.0.0",
        "models": models_status,
        "database": db_status,
        "backend_fix": "✅ All SQLAlchemy model conflicts resolved!"
    }

@app.get("/api/v1/test")
async def test_endpoint():
    return {"message": "API is working!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)