# api/main.py
# The entry point of our FastAPI application.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(
    title       = "DTU Academic Intelligence API",
    description = "API for DTU examination results and student academic profiles",
    version     = "0.1.0",
)

# CORS — allows our Next.js frontend to call this API
# Without this, browsers block cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],  # Tighten this in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# Register all routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name":    "DTU Academic Intelligence Platform",
        "version": "0.1.0",
        "status":  "running",
        "docs":    "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)