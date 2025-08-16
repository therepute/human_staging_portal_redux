from typing import Dict, Any

from fastapi import APIRouter

from .queue import queue_singleton


router = APIRouter(prefix="/api/direct", tags=["direct-search"])


@router.get("/publication/next", response_model=Dict[str, Any])
async def get_next_publication() -> Dict[str, Any]:
    pub = queue_singleton.next()
    if not pub:
        return {"success": False, "message": "No publications available"}
    return {"success": True, "publication": pub}


