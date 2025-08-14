#!/usr/bin/env python3
"""
Human Staging Portal - Main FastAPI Server
Provides endpoints for Retool integration and human scraper task management
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from urllib.parse import urlparse
import yaml
import uvicorn
import logging

from .utils.database_connector import DatabaseConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global database connector
db_connector: Optional[DatabaseConnector] = None

# Global cache of subscription credentials loaded from YAML
subscription_credentials_index: Dict[str, Dict[str, Any]] = {}
subscription_name_index: Dict[str, Dict[str, Any]] = {}


def _normalize_domain(domain: str) -> str:
    """Return a normalized registrable domain (strip protocol, path, and common subdomains)."""
    if not domain:
        return ""
    # If a URL was passed, extract netloc
    parsed = urlparse(domain if domain.startswith("http") else f"https://{domain}")
    host = parsed.netloc or parsed.path  # handle plain domain without scheme
    host = host.lower()
    # Strip common subdomains
    for prefix in ["www.", "m."]:
        if host.startswith(prefix):
            host = host[len(prefix):]
    # Keep only last two labels when possible (e.g., wired.com)
    parts = host.split(".")
    if len(parts) >= 2:
        host = ".".join(parts[-2:])
    return host


def _load_subscription_credentials(yaml_path: str) -> None:
    """Load YAML credentials and build lookup indexes by domain and by name (case-insensitive)."""
    global subscription_credentials_index, subscription_name_index
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        subs = data.get("subscriptions", [])

        domain_index: Dict[str, Dict[str, Any]] = {}
        name_index: Dict[str, Dict[str, Any]] = {}

        for entry in subs:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name") or "").strip()
            domain = (entry.get("domain") or "").strip()
            email = (entry.get("email") or "").strip()
            password = (entry.get("password") or "").strip()

            # Only index entries that at least have a domain or name
            if not (name or domain):
                continue

            normalized_domain = _normalize_domain(domain) if domain else ""
            minimal_entry = {
                "name": name,
                "domain": domain,
                "email": email,
                "password": password,
                "notes": entry.get("notes") or ""
            }

            # Prefer subscriptions@berlinrosen.com when multiple entries share a domain
            if normalized_domain:
                existing = domain_index.get(normalized_domain)
                if existing is None:
                    domain_index[normalized_domain] = minimal_entry
                else:
                    def score(e: Dict[str, Any]) -> tuple:
                        # Prefer entries with that email, then with both email+password non-empty
                        return (
                            1 if (e.get("email") == "subscriptions@berlinrosen.com") else 0,
                            1 if (e.get("email") and e.get("password")) else 0,
                        )
                    if score(minimal_entry) > score(existing):
                        domain_index[normalized_domain] = minimal_entry

            # Name index (case-insensitive, first wins unless better email)
            if name:
                key = name.lower()
                existing = name_index.get(key)
                if existing is None:
                    name_index[key] = minimal_entry
                else:
                    if existing.get("email") != "subscriptions@berlinrosen.com" and minimal_entry.get("email") == "subscriptions@berlinrosen.com":
                        name_index[key] = minimal_entry

        subscription_credentials_index = domain_index
        subscription_name_index = name_index
        logger.info(f"🔐 Loaded {len(domain_index)} credential domains and {len(name_index)} names from YAML")
    except FileNotFoundError:
        logger.warning(f"Subscription credentials YAML not found at: {yaml_path}")
    except Exception as e:
        logger.error(f"Failed to load subscription credentials: {e}")


def _find_credentials_for_article(permalink_url: Optional[str], publication: Optional[str]) -> Optional[Dict[str, Any]]:
    """Lookup credentials for the article by domain first, then by publication name."""
    # Try domain from URL
    if permalink_url:
        try:
            domain = _normalize_domain(permalink_url)
            if domain and subscription_credentials_index:
                cred = subscription_credentials_index.get(domain)
                if cred and (cred.get("email") or cred.get("password")):
                    return cred
        except Exception as e:
            logger.debug(f"Domain parse failed for URL {permalink_url}: {e}")

    # Fallback: publication name
    if publication and subscription_name_index:
        cred = subscription_name_index.get(publication.lower())
        if cred and (cred.get("email") or cred.get("password")):
            return cred

    return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database connection on startup"""
    global db_connector
    try:
        db_connector = DatabaseConnector()
        # Attempt to load subscription credentials YAML (one directory up from this file)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.abspath(os.path.join(base_dir, "..", "login_credentials.yaml"))
        _load_subscription_credentials(yaml_path)
        logger.info("✅ Human Staging Portal API started successfully")
        yield
    except Exception as e:
        logger.error(f"❌ Failed to initialize database connector: {e}")
        raise
    finally:
        logger.info("🔄 Human Staging Portal API shutting down")

# Initialize FastAPI app
app = FastAPI(
    title="Human Staging Portal API",
    description="Task assignment and content submission API for human scrapers",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files and templates
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Add CORS middleware for Retool integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Retool
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class TaskResponse(BaseModel):
    success: bool
    task: Optional[Dict[str, Any]] = None
    message: str

class SubmissionRequest(BaseModel):
    task_id: str
    scraper_id: str
    headline: Optional[str] = None
    author: Optional[str] = None
    body: Optional[str] = None
    publication: Optional[str] = None
    date: Optional[str] = None
    story_link: Optional[str] = None
    search: Optional[str] = None  # Added: subscription_source field
    source: Optional[str] = None  # Added: source field  
    client_priority: Optional[int] = None  # Added: client_priority field
    pub_tier: Optional[int] = None  # Added: pub_tier field
    duration_sec: Optional[int] = None

class FailureRequest(BaseModel):
    task_id: str
    scraper_id: str
    error_message: str

class StatusResponse(BaseModel):
    status: str
    tasks_available: int
    system_health: str

def get_db():
    """Dependency to get database connector"""
    if db_connector is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db_connector

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard interface"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/", response_model=Dict[str, str])
async def api_root():
    """API health check endpoint"""
    return {
        "service": "Human Staging Portal API",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/health", response_model=StatusResponse)
async def health_check(db: DatabaseConnector = Depends(get_db)):
    """Detailed health check with system status"""
    try:
        # Test database connection
        connection_ok = await db.test_connection()
        
        # Count available tasks
        tasks = await db.get_available_tasks(limit=100)
        tasks_count = len(tasks)
        
        return StatusResponse(
            status="healthy" if connection_ok else "unhealthy",
            tasks_available=tasks_count,
            system_health="operational" if connection_ok else "database_error"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return StatusResponse(
            status="unhealthy",
            tasks_available=0,
            system_health=f"error: {str(e)}"
        )

@app.get("/api/tasks/next", response_model=TaskResponse)
async def get_next_task(scraper_id: str, db: DatabaseConnector = Depends(get_db)):
    """Get the next highest priority task for a scraper"""
    try:
        # Get available tasks
        tasks = await db.get_available_tasks(limit=1)
        
        if not tasks:
            return TaskResponse(
                success=False,
                message="No tasks available at this time"
            )
        
        task = tasks[0]
        task_id = task["id"]
        
        # Try to assign the task
        assigned = await db.assign_task(task_id, scraper_id)
        
        if assigned:
            # Add assignment metadata
            task["assigned_at"] = datetime.now(timezone.utc).isoformat()
            task["scraper_id"] = scraper_id
            # Attach subscription credentials if available
            try:
                cred = _find_credentials_for_article(task.get("permalink_url"), task.get("publication"))
                if cred:
                    # Only include minimal, single-entry credentials
                    task["credentials"] = {
                        "name": cred.get("name"),
                        "domain": cred.get("domain"),
                        "email": cred.get("email"),
                        "password": cred.get("password"),
                        "notes": cred.get("notes"),
                    }
            except Exception as e:
                logger.warning(f"Unable to attach credentials for task {task_id}: {e}")
            
            return TaskResponse(
                success=True,
                task=task,
                message=f"Task {task_id} assigned successfully"
            )
        else:
            return TaskResponse(
                success=False,
                message="Task assignment failed - may have been taken by another scraper"
            )
            
    except Exception as e:
        logger.error(f"Error getting next task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/available", response_model=Dict[str, Any])
async def get_available_tasks(limit: int = 10, db: DatabaseConnector = Depends(get_db)):
    """Get list of available tasks (for monitoring)"""
    try:
        tasks = await db.get_available_tasks(limit=limit)
        
        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting available tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/submit", response_model=Dict[str, Any])
async def submit_extraction(submission: SubmissionRequest, db: DatabaseConnector = Depends(get_db)):
    """Submit extracted content for a task"""
    try:
        logger.info(f"🚀 SUBMIT ENDPOINT: Received submission for task {submission.task_id}")
        logger.info(f"📋 Raw submission data: {submission.model_dump()}")
        
        # Prepare extracted data
        extracted_data = {
            "headline": submission.headline,
            "author": submission.author,
            "body": submission.body,
            "publication": submission.publication,
            "date": submission.date,
            "story_link": submission.story_link,
            "search": submission.search,  # Add search field
            "source": submission.source,  # Add source field
            "client_priority": submission.client_priority,  # Add client_priority field
            "pub_tier": submission.pub_tier,  # Add pub_tier field
            "duration_sec": submission.duration_sec
        }
        
        logger.info(f"📤 Prepared extracted_data: {extracted_data}")
        
        # Submit to database
        success = await db.submit_extraction(
            submission.task_id, 
            submission.scraper_id, 
            extracted_data
        )
        
        logger.info(f"✅ Database submit_extraction returned: {success}")
        
        if success:
            return {
                "success": True,
                "message": f"Task {submission.task_id} submitted successfully",
                "task_id": submission.task_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            logger.error(f"❌ Database submit_extraction returned False for task {submission.task_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to submit task {submission.task_id}"
            )
            
    except Exception as e:
        logger.error(f"💥 Exception in submit endpoint for task {submission.task_id}: {e}")
        logger.error(f"💥 Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"💥 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/fail", response_model=Dict[str, Any])
async def fail_task(failure: FailureRequest, db: DatabaseConnector = Depends(get_db)):
    """Mark a task as failed with error details"""
    try:
        success = await db.handle_failure(
            failure.task_id,
            failure.scraper_id,
            failure.error_message
        )
        
        if success:
            return {
                "success": True,
                "message": f"Task {failure.task_id} marked as failed",
                "task_id": failure.task_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to mark task {failure.task_id} as failed"
            )
            
    except Exception as e:
        logger.error(f"Error failing task {failure.task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scrapers/{scraper_id}/tasks", response_model=Dict[str, Any])
async def get_scraper_tasks(scraper_id: str, db: DatabaseConnector = Depends(get_db)):
    """Get all tasks currently assigned to a specific scraper"""
    try:
        tasks = await db.get_scraper_tasks(scraper_id)
        
        return {
            "success": True,
            "scraper_id": scraper_id,
            "count": len(tasks),
            "tasks": tasks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting tasks for scraper {scraper_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/fields", response_model=Dict[str, Any])
async def analyze_task_fields(task_id: str, db: DatabaseConnector = Depends(get_db)):
    """Analyze which fields are required vs pre-filled for smart field detection"""
    try:
        field_analysis = await db.analyze_required_fields(task_id)
        
        if "error" in field_analysis:
            raise HTTPException(status_code=404, detail=field_analysis["error"])
        
        return {
            "success": True,
            "task_id": task_id,
            "analysis": field_analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing fields for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task_details(task_id: str, db: DatabaseConnector = Depends(get_db)):
    """Get details for a specific task"""
    try:
        task = await db.get_task_by_id(task_id)
        
        if task:
            return {
                "success": True,
                "task": task,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/maintenance/release-expired", response_model=Dict[str, Any])
async def release_expired_tasks(timeout_minutes: int = 30, db: DatabaseConnector = Depends(get_db)):
    """Release tasks that have been assigned but not completed within timeout"""
    try:
        released_count = await db.release_expired_tasks(timeout_minutes)
        
        return {
            "success": True,
            "released_count": released_count,
            "timeout_minutes": timeout_minutes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error releasing expired tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task to periodically release expired tasks
async def periodic_maintenance():
    """Background task to release expired tasks every 10 minutes"""
    while True:
        try:
            if db_connector:
                released = await db_connector.release_expired_tasks(30)
                if released > 0:
                    logger.info(f"Released {released} expired tasks")
        except Exception as e:
            logger.error(f"Periodic maintenance error: {e}")
        
        # Wait 10 minutes
        await asyncio.sleep(600)

@app.on_event("startup")
async def start_background_tasks():
    """Start background maintenance tasks"""
    asyncio.create_task(periodic_maintenance())

if __name__ == "__main__":
    # For development - use environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8001"))
    
    logger.info(f"🚀 Starting Human Staging Portal API on {host}:{port}")
    
    uvicorn.run(
        "main_api:app",
        host=host,
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    ) 