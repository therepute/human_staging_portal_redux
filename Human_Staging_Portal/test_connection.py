#!/usr/bin/env python3
"""
Test script to verify Human Staging Portal database connection
and check for articles ready for human extraction
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database_connector import DatabaseConnector
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test database connection and look for human extraction tasks"""
    
    try:
        # Initialize database connector
        logger.info("Initializing database connector...")
        db = DatabaseConnector()
        
        # Test basic connection
        logger.info("Testing database connection...")
        connection_ok = await db.test_connection()
        
        if not connection_ok:
            logger.error("❌ Database connection failed!")
            return False
        
        logger.info("✅ Database connection successful!")
        
        # Check for articles with extraction_path=2
        logger.info("Searching for articles with extraction_path=2...")
        tasks = await db.get_available_tasks(limit=10)
        
        if tasks:
            logger.info(f"✅ Found {len(tasks)} articles ready for human extraction!")
            
            # Show details of first few tasks
            for i, task in enumerate(tasks[:3]):
                logger.info(f"\nTask {i+1}:")
                logger.info(f"  ID: {task.get('id')}")
                logger.info(f"  Title: {task.get('title', 'N/A')[:100]}...")
                logger.info(f"  Publication: {task.get('publication', 'N/A')}")
                logger.info(f"  Client Priority: {task.get('client_priority', 'N/A')}")
                logger.info(f"  Pub Tier: {task.get('pub_tier', 'N/A')}")
                logger.info(f"  Source: {task.get('source', 'N/A')}")
                logger.info(f"  URL: {task.get('permalink_url', 'N/A')}")
        else:
            logger.warning("⚠️  No articles found with extraction_path=2")
            
            # Let's also check how many total articles exist in soup_dedupe
            logger.info("Checking total articles in soup_dedupe...")
            try:
                response = db.client.table(db.staging_table).select("id").limit(1).execute()
                if response.data:
                    logger.info("✅ soup_dedupe table accessible")
                    
                    # Check for any articles with extraction_path=2 regardless of other filters
                    response = db.client.table(db.staging_table).select("id, extraction_path, status, WF_Pre_Check_Complete").eq("extraction_path", 2).limit(5).execute()
                    if response.data:
                        logger.info(f"Found {len(response.data)} articles with extraction_path=2 (any status):")
                        for article in response.data:
                            logger.info(f"  ID: {article['id']}, Status: {article.get('status')}, WF_Pre_Check: {article.get('WF_Pre_Check_Complete')}")
                    else:
                        logger.info("No articles found with extraction_path=2 at all")
                else:
                    logger.error("❌ Cannot access soup_dedupe table")
            except Exception as e:
                logger.error(f"Error checking soup_dedupe: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting Human Staging Portal Database Test")
    logger.info("=" * 60)
    
    success = await test_database_connection()
    
    if success:
        logger.info("=" * 60)
        logger.info("✅ All tests passed! Human Staging Portal is ready.")
    else:
        logger.info("=" * 60)
        logger.error("❌ Tests failed. Please check configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 