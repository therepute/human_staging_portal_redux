# Task Claim Management Guide

## Overview

The Human Staging Portal uses a claim-based system to prevent multiple scrapers from working on the same task. However, claims can get "stuck" if scrapers don't complete or release them.

## Problem: Stuck Claims

**Symptoms:**
- "No articles available at this time" message
- Debug logs show high `failed_not_claimed` count
- Tasks exist but can't be assigned

**Causes:**
- Browser crashes
- User closes tab without submitting
- Network interruptions
- Server restarts during active sessions

## Automatic Prevention (Already Implemented)

### 1. Background Maintenance Task
The system automatically releases expired claims:
- **Runs every:** 5 minutes
- **Timeout:** 15 minutes (tasks claimed for >15 minutes are released)
- **Started:** Automatically on server startup

You'll see logs like:
```
🔓 MAINTENANCE: Released 5 expired tasks (claimed >15 min ago)
```

### 2. How It Works
```python
# Every 5 minutes
async def periodic_maintenance():
    # Release tasks claimed for more than 15 minutes
    released = await db_connector.release_expired_tasks(15)
    if released > 0:
        logger.info(f"Released {released} expired tasks")
```

## Manual Solutions

### Option 1: API Endpoint (Recommended)

Release all expired claims immediately:

```bash
# Release tasks claimed for more than 30 minutes
curl -X POST "https://your-api.com/api/maintenance/release-expired?timeout_minutes=30"

# Release tasks claimed for more than 10 minutes (more aggressive)
curl -X POST "https://your-api.com/api/maintenance/release-expired?timeout_minutes=10"
```

Response:
```json
{
  "success": true,
  "released_count": 123,
  "timeout_minutes": 30,
  "timestamp": "2025-10-10T10:30:00Z"
}
```

### Option 2: Unclaim Specific Task

If a user accidentally claims a task they can't complete:

```bash
curl -X POST "https://your-api.com/api/tasks/{task_id}/unclaim"
```

Response:
```json
{
  "success": true,
  "task_id": "GA_20251010_061823_000001",
  "message": "Task unclaimed successfully",
  "timestamp": "2025-10-10T10:30:00Z"
}
```

### Option 3: Check Expired Tasks (Diagnostic)

See how many claims are expired without releasing them:

```bash
curl -X GET "https://your-api.com/api/maintenance/expired-tasks?timeout_minutes=30"
```

Response:
```json
{
  "success": true,
  "expired_count": 45,
  "timeout_minutes": 30,
  "message": "45 tasks have been claimed for more than 30 minutes"
}
```

## Monitoring

### Key Metrics to Watch

1. **Debug Stats in Logs:**
```json
{
  "total_rows": 2000,
  "failed_not_claimed": 913,  // ⚠️ High number = many stuck claims
  "passed_basic_checks": 1087,
  "has_target_client": 723
}
```

2. **Maintenance Logs:**
```
✓ MAINTENANCE: No expired tasks to release  // Good - no stuck claims
🔓 MAINTENANCE: Released 15 expired tasks   // Normal - some cleanup needed
❌ MAINTENANCE ERROR: ...                   // Bad - investigate issue
```

## Configuration

### Adjust Timeouts

Edit `Human_Staging_Portal/main_api.py`:

```python
# Background maintenance
async def periodic_maintenance():
    # Change timeout (default: 15 minutes)
    released = await db_connector.release_expired_tasks(15)  # ← Adjust this
    
    # Change frequency (default: 5 minutes)
    await asyncio.sleep(300)  # ← Adjust this (in seconds)
```

**Recommended Settings:**
- **Production:** 15-minute timeout, 5-minute check frequency (current)
- **Development:** 5-minute timeout, 2-minute check frequency (faster cleanup)
- **High Traffic:** 10-minute timeout, 3-minute check frequency (more aggressive)

## Best Practices

### For Scrapers (Users)
1. **Complete or abandon:** Always submit results or close properly
2. **Don't hoard tasks:** Only claim what you can complete
3. **Use unclaim endpoint:** If you can't complete, use the unclaim API

### For Admins
1. **Monitor logs:** Watch for high `failed_not_claimed` counts
2. **Adjust timeouts:** Balance between user work time and task availability
3. **Regular maintenance:** If issues persist, manually release expired claims
4. **Database cleanup:** Periodically check for very old incomplete tasks

## Troubleshooting

### Issue: No articles available

**Check 1: How many claims are stuck?**
```bash
curl "https://your-api.com/api/maintenance/expired-tasks?timeout_minutes=15"
```

**Check 2: Release expired claims**
```bash
curl -X POST "https://your-api.com/api/maintenance/release-expired?timeout_minutes=15"
```

**Check 3: More aggressive release (if needed)**
```bash
curl -X POST "https://your-api.com/api/maintenance/release-expired?timeout_minutes=5"
```

### Issue: Maintenance task not running

**Symptoms:**
- No maintenance logs in output
- Claims never expire

**Solution:**
1. Check server logs for startup errors
2. Verify `@app.on_event("startup")` is being called
3. Restart the server

### Issue: Too many false releases

**Symptoms:**
- Users losing claimed tasks before completion
- Frequent "task already claimed" errors

**Solution:**
1. Increase timeout (e.g., from 15 to 20 minutes)
2. Decrease check frequency (e.g., from 5 to 10 minutes)

## Emergency: Release ALL Claims

⚠️ **Use only in emergency situations** (e.g., after major outage, database migration, background task not working)

Create a script `force_release_all_claims.py`:

```python
"""
Force release ALL current claims (regardless of age)
Use when tasks are stuck and you need immediate availability
"""
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", os.getenv("SUPABASE_DB_HOST", "aws-0-us-west-1.pooler.supabase.com"))
DB_NAME = os.getenv("DB_NAME", os.getenv("SUPABASE_DB_NAME", "postgres"))
DB_USER = os.getenv("DB_USER", os.getenv("SUPABASE_DB_USER", "postgres.nuumgwdbiifwsurioavm"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("SUPABASE_DB_PASSWORD", "m8$qMYGjMGkFFk8C"))
DB_PORT = int(os.getenv("DB_PORT", os.getenv("SUPABASE_DB_PORT", "5432")))

def force_release_all():
    """Force release ALL claims regardless of age"""
    try:
        print("[INFO] Connecting to database...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        
        print("[OK] Connected to database")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Count all current claims
            count_query = """
            SELECT COUNT(*) as total
            FROM soup_dedupe
            WHERE extraction_path = 2
              AND dedupe_status = 'original'
              AND "WF_Pre_Check_Complete" = TRUE
              AND ("WF_Patch_Duplicate_Syndicate" = 'creator' OR "WF_Patch_Duplicate_Syndicate" = 'unknown')
              AND wf_timestamp_claimed_at IS NOT NULL
              AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
            """
            
            cur.execute(count_query)
            result = cur.fetchone()
            total_claims = result['total'] if result else 0
            
            print(f"[INFO] Found {total_claims} tasks with active claims")
            
            if total_claims == 0:
                print("[OK] No claims to release")
                conn.close()
                return 0
            
            print(f"[INFO] Force releasing ALL {total_claims} claims (regardless of age)...")
            
            # Release ALL claims (no time filter)
            release_query = """
            UPDATE soup_dedupe
            SET wf_timestamp_claimed_at = NULL
            WHERE extraction_path = 2
              AND dedupe_status = 'original'
              AND "WF_Pre_Check_Complete" = TRUE
              AND ("WF_Patch_Duplicate_Syndicate" = 'creator' OR "WF_Patch_Duplicate_Syndicate" = 'unknown')
              AND wf_timestamp_claimed_at IS NOT NULL
              AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
            """
            
            cur.execute(release_query)
            conn.commit()
            
            rows_affected = cur.rowcount
            print(f"[OK] Force released {rows_affected} claims")
            
        conn.close()
        return rows_affected
        
    except Exception as e:
        print(f"[ERROR] Failed to release claims: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    print("=" * 60)
    print("FORCE RELEASE ALL TASK CLAIMS (NO TIME LIMIT)")
    print("=" * 60)
    print()
    
    released = force_release_all()
    
    print()
    print("=" * 60)
    print(f"COMPLETED: Force released {released} claims")
    print("=" * 60)
```

Run: `python force_release_all_claims.py`

## Summary

✅ **Automatic:** Background task releases claims every 5 minutes (15-minute timeout)  
✅ **Manual API:** Release expired claims on demand  
✅ **Per-Task:** Users can unclaim specific tasks  
✅ **Monitoring:** Check expired counts without releasing  

**The system should self-manage claims with minimal intervention!**

