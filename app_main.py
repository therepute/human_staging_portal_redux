#!/usr/bin/env python3
"""
Entry point for Railway deployment
Imports the FastAPI app from Human_Staging_Portal module
"""
# Import the FastAPI app from the Human_Staging_Portal module
from Human_Staging_Portal.main_api import app

# Export the app for uvicorn
__all__ = ['app']

if __name__ == "__main__":
    import uvicorn
    import os
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
