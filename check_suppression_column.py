#!/usr/bin/env python3
"""
Check what values exist in WF_Patch_Duplicate_Syndicate column
"""

import os
import sys
from datetime import datetime, timezone, timedelta
import asyncio

# Add the Human_Staging_Portal directory to Python path
sys.path.insert(0, 'Human_Staging_Portal')

from utils.database_connector import DatabaseConnector

async def check_suppression_column():
    """Check what values exist in WF_Patch_Duplicate_Syndicate column"""
    
    print(f"🔍 Checking WF_Patch_Duplicate_Syndicate column values")
    print(f"{'='*60}")
    
    db = DatabaseConnector()
    
    try:
        # Check if column exists and what values it has
        response = (
            db.client
            .table(db.staging_table)
            .select("id, WF_Patch_Duplicate_Syndicate, created_at")
            .eq("extraction_path", 2)
            .eq("dedupe_status", "original")
            .not_.is_("WF_Patch_Duplicate_Syndicate", "null")  # Only non-null values
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        
        rows = response.data or []
        print(f"📊 Found {len(rows)} articles with non-null WF_Patch_Duplicate_Syndicate values:")
        
        if rows:
            values_count = {}
            for row in rows:
                value = row.get("WF_Patch_Duplicate_Syndicate")
                created = row.get("created_at")
                article_id = row.get("id")
                
                if value in values_count:
                    values_count[value] += 1
                else:
                    values_count[value] = 1
                
                print(f"   📄 {article_id}: '{value}' (created: {created})")
            
            print(f"\n📈 Value distribution:")
            for value, count in values_count.items():
                print(f"   '{value}': {count} articles")
                
        else:
            print("❌ No articles found with non-null WF_Patch_Duplicate_Syndicate values")
            
            # Check if column exists at all by trying to select it
            try:
                test_response = (
                    db.client
                    .table(db.staging_table)
                    .select("WF_Patch_Duplicate_Syndicate")
                    .limit(1)
                    .execute()
                )
                print("✅ Column exists but all values are NULL")
            except Exception as e:
                print(f"❌ Column might not exist: {e}")
        
        # Also check specifically for "suppressed" values
        suppressed_response = (
            db.client
            .table(db.staging_table)
            .select("id, created_at", count="exact")
            .eq("extraction_path", 2)
            .eq("WF_Patch_Duplicate_Syndicate", "suppressed")
            .execute()
        )
        
        suppressed_count = suppressed_response.count or 0
        print(f"\n🚫 Total articles with WF_Patch_Duplicate_Syndicate = 'suppressed': {suppressed_count}")
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_suppression_column())

