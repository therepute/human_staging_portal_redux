#!/usr/bin/env python3
"""
Railway deployment server runner
Imports and runs the Human Staging Portal FastAPI app
"""

import os
import sys
import uvicorn

# Add current directory to Python path
sys.path.insert(0, '.')

# Import the FastAPI app
from Human_Staging_Portal.main_api import app

if __name__ == "__main__":
    # Get port from Railway environment
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"🚀 Starting Human Staging Portal on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=True
    )
