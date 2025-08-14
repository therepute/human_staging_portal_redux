#!/usr/bin/env python3
"""
Human Staging Portal Startup Script
Simple script to start the portal with environment variables loaded
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

def main():
    """Start the Human Staging Portal API server"""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Check for required environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or environment")
        sys.exit(1)
    
    # Configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = os.getenv("API_PORT", "8001")
    
    print("🚀 Starting Human Staging Portal API...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"📊 Health: http://{host}:{port}/api/health")
    print(f"📋 Tasks: http://{host}:{port}/api/tasks/available")
    print("=" * 60)
    
    try:
        # Start the FastAPI server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "main_api:app",
            "--host", host,
            "--port", str(port),
            "--reload"
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Human Staging Portal API stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 