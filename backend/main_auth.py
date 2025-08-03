"""Backend with working authentication endpoints."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Set environment
os.environ['DISABLE_ML'] = 'true'

app = FastAPI(
    title="AgencyDark API",
    description="Backend with authentication",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import only the auth endpoint
try:
    from api.v1.endpoints.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    print("✅ Auth endpoints loaded at /api/v1/auth")
except Exception as e:
    print(f"❌ Failed to load auth endpoints: {e}")

@app.get("/")
def read_root():
    return {"message": "AgencyDark Backend is running!"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "auth_endpoints": "available"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)