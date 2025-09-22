#!/usr/bin/env python3
"""
Check count of eligible articles from last 48 hours
"""

import os
import sys
from datetime import datetime, timezone, timedelta
import asyncio

# Add the Human_Staging_Portal directory to Python path
sys.path.insert(0, 'Human_Staging_Portal')

from utils.database_connector import DatabaseConnector

async def check_eligible_count():
    """Check how many articles from last 48 hours are currently eligible"""
    
    # Calculate 48 hours ago
    now = datetime.now(timezone.utc)
    cutoff_48h = now - timedelta(hours=48)
    
    print(f"🔍 Checking eligible articles from last 48 hours")
    print(f"📅 Current time: {now.isoformat()}")
    print(f"📅 48h cutoff: {cutoff_48h.isoformat()}")
    print(f"{'='*60}")
    
    db = DatabaseConnector()
    
    try:
        # Query with all current eligibility criteria + 48h filter
        response = (
            db.client
            .table(db.staging_table)
            .select("id, created_at, WF_Pre_Check_Complete, WF_Extraction_Complete, wf_timestamp_claimed_at, WF_Patch_Duplicate_Syndicate, WF_TIMESTAMP_Pre_Check_Complete", count="exact")
            .eq("extraction_path", 2)
            .eq("dedupe_status", "original")
            .eq("WF_Pre_Check_Complete", True)
            .neq("WF_Patch_Duplicate_Syndicate", "suppressed")  # New suppression filter
            .gte("created_at", cutoff_48h.isoformat())  # Last 48 hours
            .execute()
        )
        
        total_from_48h = response.count or 0
        rows = response.data or []
        
        print(f"📊 Total articles from last 48h matching server-side filters: {total_from_48h}")
        
        # Now apply client-side filters (like our get_available_tasks does)
        eligible_count = 0
        not_done_count = 0
        not_claimed_count = 0
        pre_check_aged_count = 0
        
        for row in rows:
            wf_done = row.get("WF_Extraction_Complete")
            wf_claimed = row.get("wf_timestamp_claimed_at")
            wf_pre_ts = row.get("WF_TIMESTAMP_Pre_Check_Complete")
            
            # Check if not done (NULL or FALSE)
            not_done = (wf_done is None) or (wf_done is False)
            if not_done:
                not_done_count += 1
            
            # Check if not claimed
            not_claimed = (wf_claimed is None)
            if not_claimed:
                not_claimed_count += 1
            
            # Check 15-minute delay after pre-check completion
            pre_check_aged = True  # Default to True if no timestamp
            if wf_pre_ts:
                try:
                    pre_check_time = datetime.fromisoformat(wf_pre_ts.replace('Z', '+00:00'))
                    pre_check_aged = (now - pre_check_time).total_seconds() >= 900  # 15 minutes = 900 seconds
                except Exception:
                    pre_check_aged = True
            
            if pre_check_aged:
                pre_check_aged_count += 1
            
            # Final eligibility check
            if not_done and not_claimed and pre_check_aged:
                eligible_count += 1
        
        print(f"\n📋 Breakdown of {total_from_48h} articles from last 48h:")
        print(f"   ✅ Not extraction complete (NULL/FALSE): {not_done_count}")
        print(f"   ✅ Not currently claimed: {not_claimed_count}")
        print(f"   ✅ Pre-check aged (15+ min): {pre_check_aged_count}")
        print(f"\n🎯 FINAL ELIGIBLE COUNT: {eligible_count}")
        
        # Additional breakdown by suppression status
        suppressed_response = (
            db.client
            .table(db.staging_table)
            .select("id, WF_Patch_Duplicate_Syndicate", count="exact")
            .eq("extraction_path", 2)
            .eq("dedupe_status", "original")
            .eq("WF_Pre_Check_Complete", True)
            .eq("WF_Patch_Duplicate_Syndicate", "suppressed")  # Only suppressed ones
            .gte("created_at", cutoff_48h.isoformat())  # Last 48 hours
            .execute()
        )
        
        suppressed_count = suppressed_response.count or 0
        print(f"\n🚫 Articles EXCLUDED by suppression filter: {suppressed_count}")
        print(f"📈 Would be eligible without suppression filter: {eligible_count + suppressed_count}")
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return
    
    print(f"\n{'='*60}")
    print(f"✅ Query completed successfully")

if __name__ == "__main__":
    asyncio.run(check_eligible_count())

