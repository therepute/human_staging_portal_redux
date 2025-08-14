"""
Database Connector for Human Staging Portal
Handles connection to Supabase with soup_dedupe (staging) and the_soups (destination) tables
"""
import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseConnector:
    def __init__(self):
        """Initialize Supabase client with credentials"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.staging_table = "soup_dedupe"
        self.destination_table = "the_soups"
        
        logger.info(f"Initialized database connector for {self.supabase_url}")

    async def get_available_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch articles from soup_dedupe where extraction_path=2 and WF_Pre_Check_Complete is True
        Handles both boolean True and string "TRUE" values for WF_Pre_Check_Complete
        """
        try:
            # Query for articles ready for human extraction (exclude completed ones)
            response = self.client.table(self.staging_table).select(
                "id, title, permalink_url, published_at, source_title, source_url, "
                "summary, content, subscription_source, source, client_priority, "
                "headline_relevance, pub_tier, publication, clients, retry_count, "
                "next_retry_at, last_modified, created_at"
            ).eq("extraction_path", 2).or_(
                "WF_Pre_Check_Complete.eq.true,WF_Pre_Check_Complete.eq.TRUE"
            ).or_(
                "WF_Extraction_Complete.is.null,WF_Extraction_Complete.eq.false"
            ).order("client_priority", desc=True).order("created_at", desc=True).limit(limit).execute()
            
            if response.data:
                logger.info(f"Found {len(response.data)} available tasks")
                return response.data
            else:
                logger.info("No available tasks found")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching available tasks: {e}")
            return []

    async def assign_task(self, task_id: str, scraper_id: str) -> bool:
        """
        Simplified task assignment - just return the task without database updates
        (Working with existing soup_dedupe schema without scraper_id/assigned_at columns)
        """
        try:
            # Verify the task exists and is available (not completed)
            response = self.client.table(self.staging_table).select("id").eq("id", task_id).eq("extraction_path", 2).or_(
                "WF_Extraction_Complete.is.null,WF_Extraction_Complete.eq.false"
            ).limit(1).execute()
            
            if response.data:
                logger.info(f"Task {task_id} assigned to scraper {scraper_id} (simplified mode)")
                return True
            else:
                logger.warning(f"Task {task_id} not found or not available for assignment")
                return False
                
        except Exception as e:
            logger.error(f"Error checking task {task_id}: {e}")
            return False

    async def submit_extraction(self, task_id: str, scraper_id: str, extracted_data: Dict[str, Any]) -> bool:
        """
        Submit extracted content to the_soups table and update soup_dedupe status
        Maps fields according to user specifications: soup_dedupe → the_soups
        """
        try:
            logger.info(f"🚀 Starting submission for task {task_id}")
            logger.info(f"📋 Extracted data received: {extracted_data}")
            
            current_time = datetime.now(timezone.utc).isoformat()
            
            # First, get the original article data
            original_response = self.client.table(self.staging_table).select("*").eq("id", task_id).execute()
            
            if not original_response.data:
                logger.error(f"❌ Original article {task_id} not found")
                return False
            
            original_article = original_response.data[0]
            logger.info(f"📰 Original article data: {original_article}")
            
            # Prepare data for the_soups table - EXACT USER MAPPING:
            soups_data = {
                # Core required fields per user specification
                "Date": None if extracted_data.get("date") == "Not Available" else (extracted_data.get("date") or (original_article.get("published_at", "").split("T")[0] if original_article.get("published_at") else None)),
                "Publication": extracted_data.get("publication") or original_article.get("publication"),  # Scraper OR existing publication
                "Author": extracted_data.get("author") or original_article.get("actor_name"),  # Scraper OR existing actor_name
                "Headline": extracted_data.get("headline") or original_article.get("title"),  # Scraper OR existing title
                "Body": extracted_data.get("body"),  # ALWAYS from scraper
                "Story_Link": original_article.get("permalink_url"),  # Direct carryover
                "Search": original_article.get("subscription_source"),  # Direct carryover ✅
                "Source": original_article.get("source"),  # Direct carryover from 'source' field ✅
                "client_priority": original_article.get("client_priority"),  # Direct carryover ✅
                "subscription": original_article.get("subscription"),  # Direct carryover ✅
                # "pub_tier": original_article.get("pub_tier"),  # REMOVED: Column doesn't exist in the_soups table
                "soup_dedupe_id": task_id  # Links back to soup_dedupe.id ✅
            }
            
            logger.info(f"🗂️ Mapped soups_data (before cleanup): {soups_data}")
            
            # Remove None values for clean insertion
            soups_data = {k: v for k, v in soups_data.items() if v is not None}
            
            logger.info(f"🗂️ Final soups_data (after cleanup): {soups_data}")
            logger.info(f"📊 Inserting into table: {self.destination_table}")
            
            # Insert into the_soups
            insert_response = self.client.table(self.destination_table).insert(soups_data).execute()
            
            logger.info(f"📤 Insert response: {insert_response}")
            
            if not insert_response.data:
                logger.error(f"❌ Failed to insert into {self.destination_table} - no data returned")
                logger.error(f"❌ Insert response details: {insert_response}")
                return False
            
            logger.info(f"✅ Successfully inserted into {self.destination_table}: {insert_response.data}")
            
            # Update soup_dedupe status to completed
            update_data = {
                "extraction_path": 3,  # Mark as completed
                "WF_Extraction_Complete": True,
                "last_modified": current_time
            }
            logger.info(f"🔄 Updating soup_dedupe with: {update_data}")
            
            update_response = self.client.table(self.staging_table).update(update_data).eq("id", task_id).execute()
            
            logger.info(f"🔄 Update response: {update_response}")
            
            if update_response.data:
                logger.info(f"✅ Successfully submitted extraction for task {task_id}")
                return True
            else:
                logger.error(f"❌ Failed to update status for task {task_id}")
                logger.error(f"❌ Update response details: {update_response}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Error submitting extraction for task {task_id}: {e}")
            logger.error(f"💥 Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"💥 Full traceback: {traceback.format_exc()}")
            return False

    async def handle_failure(self, task_id: str, scraper_id: str, error_message: str) -> bool:
        """
        Handle extraction failure by marking as complete (unable to extract)
        This removes the article from the available queue
        """
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Mark as extraction complete (even though failed) to remove from queue
            update_data = {
                "WF_Extraction_Complete": True,  # Mark as processed/complete
                "WF_Extraction_Complete_Explanation": error_message,  # Capture rejection reason
                "last_modified": current_time,
                "WF_TIMESTAMP_Extraction_Complete": current_time  # Set completion timestamp
            }
            
            # Try to increment retry_count if it exists
            try:
                response = self.client.table(self.staging_table).select("retry_count").eq("id", task_id).execute()
                if response.data and len(response.data) > 0:
                    current_retry_count = response.data[0].get("retry_count", 0)
                    update_data["retry_count"] = current_retry_count + 1
            except Exception as e:
                logger.warning(f"Could not update retry_count for {task_id}: {e}")
            
            update_response = self.client.table(self.staging_table).update(update_data).eq("id", task_id).execute()
            
            if update_response.data:
                logger.info(f"Marked task {task_id} as unable to extract (WF_Extraction_Complete=True): {error_message}")
                return True
            else:
                logger.error(f"Failed to update failure status for task {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling failure for task {task_id}: {e}")
            return False

    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID"""
        try:
            response = self.client.table(self.staging_table).select("*").eq("id", task_id).execute()
            
            if response.data:
                return response.data[0]
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {e}")
            return None

    async def get_scraper_tasks(self, scraper_id: str) -> List[Dict[str, Any]]:
        """Get all tasks currently assigned to a scraper (simplified - no tracking)"""
        try:
            # Since we don't have scraper_id column, just return empty list
            # In a real implementation, this would track assignments in a separate table
            logger.info(f"No tasks tracked for scraper {scraper_id} (simplified mode)")
            return []
                
        except Exception as e:
            logger.error(f"Error fetching tasks for scraper {scraper_id}: {e}")
            return []

    async def release_expired_tasks(self, timeout_minutes: int = 30) -> int:
        """Release expired tasks (simplified - no task tracking)"""
        try:
            # Since we don't track task assignments in the database, just return 0
            # In a real implementation, this would use a separate tracking table
            logger.info("No expired tasks to release (simplified mode)")
            return 0
            
        except Exception as e:
            logger.error(f"Error releasing expired tasks: {e}")
            return 0

    async def analyze_required_fields(self, task_id: str) -> Dict[str, Any]:
        """
        Smart field analysis: determine which fields need human input vs. pre-filled
        Returns field requirements and pre-filled values
        """
        try:
            # Get the original article data
            response = self.client.table(self.staging_table).select("*").eq("id", task_id).execute()
            
            if not response.data:
                logger.error(f"Article {task_id} not found for field analysis")
                return {"error": "Task not found"}
            
            article = response.data[0]
            
            # Analyze each field according to user mapping requirements
            field_analysis = {
                "task_id": task_id,
                "required_fields": [],  # Fields that need human input
                "pre_filled_fields": {},  # Fields already available
                "field_sources": {}  # Track where each field comes from
            }
            
            # Date field analysis
            if article.get("published_at"):
                field_analysis["pre_filled_fields"]["date"] = article["published_at"].split("T")[0]
                field_analysis["field_sources"]["date"] = "soup_dedupe.published_at"
            else:
                field_analysis["required_fields"].append("date")
                field_analysis["field_sources"]["date"] = "scraper_required"
            
            # Publication field (always from soup_dedupe)
            if article.get("publication"):
                field_analysis["pre_filled_fields"]["publication"] = article["publication"]
                field_analysis["field_sources"]["publication"] = "soup_dedupe.publication"
            
            # Author field analysis  
            if article.get("actor_name"):
                field_analysis["pre_filled_fields"]["author"] = article["actor_name"]
                field_analysis["field_sources"]["author"] = "soup_dedupe.actor_name"
            else:
                field_analysis["required_fields"].append("author")
                field_analysis["field_sources"]["author"] = "scraper_required"
            
            # Headline field analysis
            if article.get("title"):
                field_analysis["pre_filled_fields"]["headline"] = article["title"]
                field_analysis["field_sources"]["headline"] = "soup_dedupe.title"
            else:
                field_analysis["required_fields"].append("headline")
                field_analysis["field_sources"]["headline"] = "scraper_required"
            
            # Body field (ALWAYS required from scraper)
            field_analysis["required_fields"].append("body")
            field_analysis["field_sources"]["body"] = "scraper_always_required"
            
            # Story_Link (always from soup_dedupe)
            if article.get("permalink_url"):
                field_analysis["pre_filled_fields"]["story_link"] = article["permalink_url"]
                field_analysis["field_sources"]["story_link"] = "soup_dedupe.permalink_url"
            
            logger.info(f"Field analysis for {task_id}: {len(field_analysis['required_fields'])} fields needed")
            return field_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing fields for task {task_id}: {e}")
            return {"error": str(e)}

    async def test_connection(self) -> bool:
        """Test database connection and table access"""
        try:
            # Test connection by querying a small subset
            response = self.client.table(self.staging_table).select("id").limit(1).execute()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False 