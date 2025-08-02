"""
Simplified main.py to test basic server functionality
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# Create FastAPI app
app = FastAPI(title="AgencyDark Backend (Simplified)")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "agencydark-backend",
            "version": "1.0.0"
        }
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AgencyDark Backend API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)