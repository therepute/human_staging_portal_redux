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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import urlparse
import yaml
import uvicorn
import logging

# Import DatabaseConnector in a way that works in both deployment modes:
# 1) Started from repo root (import path: Human_Staging_Portal.main_api)
# 2) Started from package dir (module name: main_api, with sibling package utils/)
try:
    from Human_Staging_Portal.utils.database_connector import DatabaseConnector  # mode 1
    from Human_Staging_Portal.utils.auth import (
        authenticate_user, register_user, create_session, get_current_user, 
        destroy_session, require_auth, get_session_stats, cleanup_expired_sessions
    )
except ModuleNotFoundError:
    from utils.database_connector import DatabaseConnector  # mode 2
    from utils.auth import (
        authenticate_user, register_user, create_session, get_current_user,
        destroy_session, require_auth, get_session_stats, cleanup_expired_sessions
    )

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global database connector
db_connector: Optional[DatabaseConnector] = None

# Safe degraded-mode stub so endpoints don't 500 when DB is unavailable
class NullDatabaseConnector:
    async def test_connection(self) -> bool:
        return False

    async def get_available_tasks(self, limit: int = 50):
        return []

    async def assign_task(self, task_id: str, scraper_id: str) -> bool:
        return False

    async def submit_extraction(self, task_id: str, scraper_id: str, extracted_data: Dict[str, Any]) -> bool:
        return False

    async def handle_failure(self, task_id: str, scraper_id: str, error_message: str) -> bool:
        return False

    async def analyze_required_fields(self, task_id: str) -> Dict[str, Any]:
        return {"task_id": task_id, "required_fields": ["body"], "pre_filled_fields": {}, "field_sources": {}}

    async def get_task_by_id(self, task_id: str):
        return None

    async def get_soups_by_soup_dedupe_id(self, task_id: str):
        return None

    async def get_scraper_tasks(self, scraper_id: str):
        return []

    async def release_expired_tasks(self, timeout_minutes: int = 30) -> int:
        return 0

null_db = NullDatabaseConnector()

# Global cache of subscription credentials loaded from YAML
subscription_credentials_index: Dict[str, Dict[str, Any]] = {}
subscription_name_index: Dict[str, Dict[str, Any]] = {}

# In-memory recent task tracker to avoid re-serving the same article immediately
RECENT_WINDOW_SECONDS = 600  # 10 minutes
recent_tasks_by_scraper: Dict[str, Dict[str, float]] = {}

def _mark_recent(scraper_id: str, task_id: str) -> None:
    import time
    bucket = recent_tasks_by_scraper.setdefault(scraper_id, {})
    bucket[task_id] = time.time()

def _prune_and_is_recent(scraper_id: str, task_id: str) -> bool:
    import time
    now = time.time()
    bucket = recent_tasks_by_scraper.get(scraper_id)
    if not bucket:
        return False
    # Prune
    expired = [tid for tid, ts in bucket.items() if now - ts > RECENT_WINDOW_SECONDS]
    for tid in expired:
        bucket.pop(tid, None)
    return task_id in bucket


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
    maintenance_task = None
    
    try:
        # Best-effort DB init: allow UI to boot even if Supabase is not configured
        try:
            db_connector = DatabaseConnector()
        except Exception as e:
            db_connector = None
            logger.error(f"❌ Failed to initialize database connector: {e}")

        # Attempt to load subscription credentials YAML (one directory up from this file)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.abspath(os.path.join(base_dir, "..", "login_credentials.yaml"))
        _load_subscription_credentials(yaml_path)

        # Start background maintenance task
        if db_connector:
            maintenance_task = asyncio.create_task(periodic_maintenance())
            logger.info("✅ Started background maintenance task (releases claims every 5 min)")

        if db_connector is None:
            logger.info("✅ Human Staging Portal API started in degraded mode (no database)")
        else:
            logger.info("✅ Human Staging Portal API started successfully")
        yield
    finally:
        # Cleanup: cancel background task
        if maintenance_task:
            maintenance_task.cancel()
            try:
                await maintenance_task
            except asyncio.CancelledError:
                pass
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

# Register feature routers
try:
    from Human_Staging_Portal.features.direct_search.router import router as direct_search_router
except ModuleNotFoundError:
    from features.direct_search.router import router as direct_search_router

app.include_router(direct_search_router)

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

class LoginRequest(BaseModel):
    email: str

class RegisterRequest(BaseModel):
    email: str
    first_name: str
    last_name: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None

def get_db():
    """Dependency to get database connector"""
    # Return a degraded-mode stub when DB isn't initialized so endpoints gracefully degrade
    return db_connector or null_db

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard interface or redirect to login"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/api/auth/login", response_model=AuthResponse)
async def login(login_request: LoginRequest, db: DatabaseConnector = Depends(get_db)):
    """Login with email (no password required)"""
    try:
        user = await authenticate_user(login_request.email, db)
        if user:
            session_token = create_session(user)
            
            # Log the login activity
            await db.log_login(user["email"])
            
            response = JSONResponse(content={
                "success": True,
                "message": "Login successful",
                "user": {
                    "email": user["email"],
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "role": user.get("role", "user")
                }
            })
            response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=8*3600)  # 8 hours
            return response
        else:
            return AuthResponse(success=False, message="User not found. Please register first.")
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/register", response_model=AuthResponse)
async def register(register_request: RegisterRequest, db: DatabaseConnector = Depends(get_db)):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = await db.get_user_by_email(register_request.email)
        if existing_user:
            return AuthResponse(success=False, message="User already exists. Please login instead.")
        
        # Register new user
        logger.info(f"Attempting to register user: {register_request.email}")
        user = await register_user(register_request.email, register_request.first_name, register_request.last_name, db)
        logger.info(f"Registration result for {register_request.email}: {user is not None}")
        if user:
            session_token = create_session(user)
            
            # Log the login activity (auto-login after registration)
            await db.log_login(user["email"])
            
            response = JSONResponse(content={
                "success": True,
                "message": "Registration successful",
                "user": {
                    "email": user["email"],
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "role": user.get("role", "user")
                }
            })
            response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=8*3600)  # 8 hours
            return response
        else:
            logger.error(f"Registration failed for {register_request.email}: register_user returned None")
            return AuthResponse(success=False, message="Registration failed. Please try again.")
    except Exception as e:
        logger.error(f"Registration error for {register_request.email}: {e}")
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Registration traceback: {tb}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
async def logout(request: Request, db: DatabaseConnector = Depends(get_db)):
    """Logout and destroy session"""
    session_token = request.cookies.get("session_token")
    user_email = None
    
    if session_token:
        # Get user info before destroying session
        user = get_current_user(request)
        if user:
            user_email = user["email"]
        
        destroy_session(session_token)
    
    # Log the logout activity if we have the user email
    if user_email:
        await db.log_logout(user_email)
    
    response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    response.delete_cookie(key="session_token")
    return response

@app.get("/api/auth/user")
async def get_current_user_api(request: Request):
    """Get current authenticated user info"""
    user = get_current_user(request)
    if user:
        return {
            "success": True,
            "user": {
                "email": user["email"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "role": user.get("role", "user")
            }
        }
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

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
async def get_next_task(request: Request, db: DatabaseConnector = Depends(get_db)):
    """Get the next highest priority task for a scraper"""
    try:
        import time
        request_start = time.time()
        
        # Require authentication
        user = require_auth(request)
        scraper_id = user["email"]  # Use email as scraper_id
        user_email = user["email"]
        
        # Get a batch of available tasks then filter out recently served
        fetch_start = time.time()
        tasks = await db.get_available_tasks(limit=50)
        fetch_elapsed = time.time() - fetch_start
        logger.info(f"Fetched {len(tasks)} tasks in {fetch_elapsed:.2f}s")
        
        if not tasks:
            # Align with frontend expectation: return 404 when no tasks
            raise HTTPException(status_code=404, detail="No tasks available at this time")
        
        # Filter out tasks recently served to this scraper (assignment or completion)
        filtered = [t for t in tasks if not _prune_and_is_recent(scraper_id, t.get("id"))]

        if not filtered:
            return TaskResponse(success=False, message="No tasks available at this time")

        # Try to assign tasks in order until one succeeds (atomic claiming)
        # Limit attempts to avoid long delays
        assigned_task = None
        max_attempts = min(10, len(filtered))  # Try max 10 tasks
        
        assign_start = time.time()
        attempts = 0
        for i, task in enumerate(filtered[:max_attempts]):
            task_id = task["id"]
            attempts += 1
            assigned = await db.assign_task(task_id, scraper_id)
            if assigned:
                assigned_task = task
                break
            # If this isn't the first attempt and we failed, add small delay
            if i > 0:
                await asyncio.sleep(0.01)  # 10ms delay between retries
        
        assign_elapsed = time.time() - assign_start
        logger.info(f"Task assignment: {'SUCCESS' if assigned_task else 'FAILED'} in {assign_elapsed:.2f}s ({attempts} attempts)")
        
        if assigned_task:
            # Add assignment metadata
            served_timestamp = datetime.now(timezone.utc).isoformat()
            assigned_task["assigned_at"] = served_timestamp
            assigned_task["scraper_id"] = scraper_id
            task_id = assigned_task["id"]
            
            # Store workflow status = 1 (opened in window) in soup_dedupe table
            try:
                await db.update_served_status(task_id, 1, user_email)
                logger.info(f"Recorded workflow status 1 (opened) for task {task_id} to user {user_email}")
            except Exception as e:
                logger.warning(f"Failed to record workflow status for task {task_id}: {e}")
            
            # Mark recent to reduce immediate reselection
            _mark_recent(scraper_id, task_id)
            # Attach subscription credentials if available
            try:
                # Use permalink domain first; fallback to publication name
                cred = _find_credentials_for_article(assigned_task.get("permalink_url"), assigned_task.get("publication"))
                if not cred and assigned_task.get("source_url"):
                    cred = _find_credentials_for_article(assigned_task.get("source_url"), assigned_task.get("publication"))
                if cred:
                    assigned_task["credentials"] = {
                        "name": cred.get("name"),
                        "domain": cred.get("domain"),
                        "email": cred.get("email"),
                        "password": cred.get("password"),
                        "notes": cred.get("notes"),
                    }
            except Exception as e:
                logger.warning(f"Unable to attach credentials for task {task_id}: {e}")
            
            total_elapsed = time.time() - request_start
            logger.info(f"TOTAL REQUEST TIME: {total_elapsed:.2f}s (fetch: {fetch_elapsed:.2f}s, assign: {assign_elapsed:.2f}s)")
            return TaskResponse(
                success=True,
                task=assigned_task,
                message=f"Task {task_id} assigned successfully"
            )
        else:
            total_elapsed = time.time() - request_start
            logger.warning(f"No tasks could be claimed after {total_elapsed:.2f}s")
            return TaskResponse(
                success=False,
                message="Task assignment failed - may have been taken by another scraper"
            )
            
    except HTTPException as he:
        # Propagate intended HTTP errors (e.g., 404 when no tasks)
        raise he
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

@app.get("/api/tasks/availability_report", response_model=Dict[str, Any])
async def availability_report(db: DatabaseConnector = Depends(get_db)):
    """Diagnostics endpoint to understand why no tasks are available."""
    try:
        if not hasattr(db, "availability_report"):
            return {"success": False, "error": "availability_report not supported in current DB mode"}
        report = await db.availability_report()
        return report
    except Exception as e:
        logger.error(f"Error generating availability report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recent", response_model=Dict[str, Any])
async def get_recent(limit: int = 50, db: DatabaseConnector = Depends(get_db)):
    """Return the most recent human-portal submissions (up to limit)."""
    try:
        limit = max(1, min(limit, 100))
        rows = await db.get_recent_human(limit)
        return {"success": True, "count": len(rows), "items": rows}
    except Exception as e:
        logger.error(f"Error getting recent list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/submit", response_model=Dict[str, Any])
async def submit_extraction(submission: SubmissionRequest, request: Request, db: DatabaseConnector = Depends(get_db)):
    """Submit extracted content for a task"""
    try:
        # Require authentication
        user = require_auth(request)
        user_email = user["email"]  # Get user email for scraper_user field
        
        logger.info(f"🚀 SUBMIT ENDPOINT: Received submission for task {submission.task_id} from user {user_email}")
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
        
        # Submit to database: scraper_id from request (human_portal_user), scraper_user is authenticated email
        success = await db.submit_extraction(
            submission.task_id, 
            submission.scraper_id,  # Use the scraper_id from request (human_portal_user)
            extracted_data,
            user_email  # Pass user email as scraper_user
        )
        
        logger.info(f"✅ Database submit_extraction returned: {success}")
        
        # Update workflow status = 2 (extraction submitted)
        if success:
            try:
                await db.update_served_status(submission.task_id, 2, user_email)
                logger.info(f"Updated workflow status to 2 (submitted) for task {submission.task_id}")
            except Exception as e:
                logger.warning(f"Failed to update workflow status for task {submission.task_id}: {e}")
        
        if success:
            # Mark as recent completion to avoid re-serving due to eventual consistency
            _mark_recent(user_email, submission.task_id)
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
        tb = traceback.format_exc()
        logger.error(f"💥 Full traceback: {tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")

@app.post("/api/tasks/fail", response_model=Dict[str, Any])
async def fail_task(failure: FailureRequest, request: Request, db: DatabaseConnector = Depends(get_db)):
    """Mark a task as failed with error details"""
    try:
        # Require authentication
        user = require_auth(request)
        user_email = user["email"]  # Get user email for scraper_user field
        
        # Use scraper_id from request (human_portal_user), scraper_user is authenticated email
        success = await db.handle_failure(
            failure.task_id,
            failure.scraper_id,  # Use the scraper_id from request (human_portal_user)
            failure.error_message,
            user_email  # Pass user email as scraper_user
        )
        
        if success:
            # Mark as recent failure to avoid re-serving
            _mark_recent(user_email, failure.task_id)
            return {
                "success": True,
                "message": f"Task {failure.task_id} successfully marked as unable to extract",
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
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Full traceback: {tb}")
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
        if not task:
            # Try the_soups via soup_dedupe_id for review-mode items
            task = await db.get_soups_by_soup_dedupe_id(task_id)
        
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

@app.get("/api/task", response_model=Dict[str, Any])
async def get_task_details_query(task_id: str, db: DatabaseConnector = Depends(get_db)):
    """Same as get_task_details, but takes task_id as a query parameter to support IDs containing slashes."""
    try:
        task = await db.get_task_by_id(task_id)
        if not task:
            task = await db.get_soups_by_soup_dedupe_id(task_id)
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
        logger.error(f"Error getting task {task_id} via query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================== Admin endpoints (read-only) =====================
@app.get("/api/admin/human_per_day", response_model=Dict[str, Any])
async def admin_human_per_day(days: int = 14, db: DatabaseConnector = Depends(get_db)):
    try:
        rows = await db.metrics_human_per_day(days)
        return {"success": True, "days": days, "items": rows}
    except Exception as e:
        logger.error(f"Admin human_per_day error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/soups_groupings", response_model=Dict[str, Any])
async def admin_soups_groupings(db: DatabaseConnector = Depends(get_db)):
    try:
        data = await db.metrics_soups_groupings()
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Admin soups_groupings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/pending_groupings", response_model=Dict[str, Any])
async def admin_pending_groupings(db: DatabaseConnector = Depends(get_db)):
    try:
        data = await db.metrics_pending_groupings()
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Admin pending_groupings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/served_metrics", response_model=Dict[str, Any])
async def admin_served_metrics(db: DatabaseConnector = Depends(get_db)):
    """Get Articles Served and Duplicates Served metrics for last 24h and 3h"""
    try:
        data = await db.metrics_served_articles()
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Admin served_metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/admin/activity_logs", response_model=Dict[str, Any])
async def admin_activity_logs(limit: int = 100, username: str = None, db: DatabaseConnector = Depends(get_db)):
    """Get activity logs (admin only)"""
    try:
        logs = await db.get_activity_logs(limit, username)
        return {
            "success": True,
            "count": len(logs),
            "logs": logs,
            "filters": {"limit": limit, "username": username}
        }
    except Exception as e:
        logger.error(f"Admin activity logs error: {e}")
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

@app.post("/api/tasks/{task_id}/unclaim", response_model=Dict[str, Any])
async def unclaim_task(task_id: str, db: DatabaseConnector = Depends(get_db)):
    """Manually release a claimed task (allows users to unclaim if they can't complete it)"""
    try:
        # Release the specific task by setting wf_timestamp_claimed_at to NULL
        update_response = (
            db.client
            .table(db.staging_table)
            .update({"wf_timestamp_claimed_at": None})
            .eq("id", task_id)
            .execute()
        )
        
        if update_response.data:
            logger.info(f"✓ Task {task_id} manually unclaimed")
            return {
                "success": True,
                "task_id": task_id,
                "message": "Task unclaimed successfully",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "success": False,
                "task_id": task_id,
                "message": "Task not found or already unclaimed"
            }
    except Exception as e:
        logger.error(f"Error unclaiming task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/maintenance/expired-tasks", response_model=Dict[str, Any])
async def check_expired_tasks(timeout_minutes: int = 30, db: DatabaseConnector = Depends(get_db)):
    """Check how many tasks are currently expired without releasing them"""
    try:
        from datetime import datetime, timezone, timedelta
        
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        cutoff_iso = cutoff_time.isoformat()
        
        # Count expired tasks
        count_response = (
            db.client
            .table(db.staging_table)
            .select("id", count="exact")
            .eq("extraction_path", 2)
            .eq("dedupe_status", "original")
            .eq("WF_Pre_Check_Complete", True)
            .in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"])  # NEW: Only creator or unknown
            .is_("WF_Extraction_Complete", "null")
            .not_.is_("wf_timestamp_claimed_at", "null")  # Must be claimed
            .lt("wf_timestamp_claimed_at", cutoff_iso)    # Claimed before cutoff
            .execute()
        )
        
        expired_count = count_response.count or 0
        
        return {
            "success": True,
            "expired_count": expired_count,
            "timeout_minutes": timeout_minutes,
            "cutoff_time": cutoff_iso,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking expired tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task to periodically release expired tasks
async def periodic_maintenance():
    """Background task to release expired tasks every 5 minutes"""
    while True:
        try:
            if db_connector:
                # Release tasks claimed for more than 15 minutes (reduced from 30)
                released = await db_connector.release_expired_tasks(15)
                if released > 0:
                    logger.info(f"🔓 MAINTENANCE: Released {released} expired tasks (claimed >15 min ago)")
                else:
                    logger.debug(f"✓ MAINTENANCE: No expired tasks to release")
        except Exception as e:
            logger.error(f"❌ MAINTENANCE ERROR: {e}")
        
        # Wait 5 minutes (reduced from 10)
        await asyncio.sleep(300)

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