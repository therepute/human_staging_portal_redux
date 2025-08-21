#!/usr/bin/env python3
"""
Authentication utilities for Human Staging Portal
Provides user authentication, session management, and login/logout functionality
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from fastapi import Request, HTTPException, status
import logging

logger = logging.getLogger(__name__)

# In-memory session store (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}

# Session timeout (8 hours for a work shift)
SESSION_TIMEOUT_HOURS = 8

async def authenticate_user(email: str, db_connector) -> Optional[Dict[str, Any]]:
    """Authenticate a user by email (no password required)"""
    user = await db_connector.get_user_by_email(email)
    if user:
        user["login_time"] = datetime.now(timezone.utc).isoformat()
        return user
    return None

async def register_user(email: str, first_name: str, last_name: str, db_connector) -> Optional[Dict[str, Any]]:
    """Register a new user in the database"""
    return await db_connector.register_user(email, first_name, last_name)

def create_session(user_info: Dict[str, Any]) -> str:
    """Create a new session and return session token"""
    session_token = secrets.token_urlsafe(32)
    session_data = {
        "user": user_info,
        "created_at": datetime.now(timezone.utc),
        "last_activity": datetime.now(timezone.utc)
    }
    sessions[session_token] = session_data
    logger.info(f"Created session for user {user_info['email']}")
    return session_token

def get_session(session_token: str) -> Optional[Dict[str, Any]]:
    """Get session data if valid and not expired"""
    if not session_token or session_token not in sessions:
        return None
    
    session_data = sessions[session_token]
    
    # Check if session has expired
    if datetime.now(timezone.utc) - session_data["created_at"] > timedelta(hours=SESSION_TIMEOUT_HOURS):
        del sessions[session_token]
        return None
    
    # Update last activity
    session_data["last_activity"] = datetime.now(timezone.utc)
    return session_data

def destroy_session(session_token: str) -> bool:
    """Destroy a session"""
    if session_token in sessions:
        user = sessions[session_token].get("user", {}).get("email", "Unknown")
        del sessions[session_token]
        logger.info(f"Destroyed session for user {user}")
        return True
    return False

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session cookie"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    
    session_data = get_session(session_token)
    if not session_data:
        return None
    
    return session_data["user"]

def require_auth(request: Request) -> Dict[str, Any]:
    """Require authentication, raise HTTPException if not authenticated"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

def require_admin(request: Request) -> Dict[str, Any]:
    """Require admin authentication"""
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

def get_session_stats() -> Dict[str, Any]:
    """Get statistics about active sessions"""
    now = datetime.now(timezone.utc)
    active_sessions = []
    
    for token, session_data in sessions.items():
        if now - session_data["created_at"] <= timedelta(hours=SESSION_TIMEOUT_HOURS):
            user = session_data["user"]
            active_sessions.append({
                "email": user["email"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "role": user["role"],
                "login_time": user["login_time"],
                "last_activity": session_data["last_activity"].isoformat(),
                "duration": str(now - session_data["created_at"]).split(".")[0]
            })
    
    return {
        "active_sessions": len(active_sessions),
        "sessions": active_sessions
    }

def cleanup_expired_sessions():
    """Clean up expired sessions"""
    now = datetime.now(timezone.utc)
    expired_tokens = [
        token for token, session_data in sessions.items()
        if now - session_data["created_at"] > timedelta(hours=SESSION_TIMEOUT_HOURS)
    ]
    
    for token in expired_tokens:
        user = sessions[token].get("user", {}).get("email", "Unknown")
        del sessions[token]
        logger.info(f"Cleaned up expired session for user {user}")
    
    return len(expired_tokens)
