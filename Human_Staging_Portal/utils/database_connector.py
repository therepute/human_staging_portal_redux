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

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user from Manual_Scrape_Users table by email"""
        try:
            response = self.client.table("Manual_Scrape_Users").select("*").eq("email", email).eq("active", True).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None

    async def register_user(self, email: str, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
        """Register a new user in Manual_Scrape_Users table"""
        try:
            user_data = {
                "username": email,  # Use email as username since we don't use separate usernames
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": "user",
                "active": True
            }
            
            response = self.client.table("Manual_Scrape_Users").insert(user_data).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Registered new user: {email}")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error registering user {email}: {e}")
            return None

    async def log_login(self, username: str) -> bool:
        """Log a login event to Manual_Scrape_Activity_Logs"""
        try:
            login_data = {
                "username": username,
                "login_time": datetime.now(timezone.utc).isoformat(),
                "logout_time": None
            }
            
            response = self.client.table("Manual_Scrape_Activity_Logs").insert(login_data).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Logged login for user: {username}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error logging login for {username}: {e}")
            return False

    async def log_logout(self, username: str) -> bool:
        """Log a logout event to Manual_Scrape_Activity_Logs"""
        try:
            logout_data = {
                "username": username,
                "login_time": None,
                "logout_time": datetime.now(timezone.utc).isoformat()
            }
            
            response = self.client.table("Manual_Scrape_Activity_Logs").insert(logout_data).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Logged logout for user: {username}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error logging logout for {username}: {e}")
            return False

    async def get_activity_logs(self, limit: int = 100, username: str = None) -> List[Dict[str, Any]]:
        """Get activity logs, optionally filtered by username"""
        try:
            query = self.client.table("Manual_Scrape_Activity_Logs").select("*").order("id", desc=True).limit(limit)
            
            if username:
                query = query.eq("username", username)
            
            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting activity logs: {e}")
            return []

    async def update_served_status(self, task_id: str, workflow_status: int, user_email: str) -> bool:
        """Update soup_dedupe with workflow status when article is served/submitted"""
        try:
            update_data = {
                "WF_served_human_scrape": workflow_status,
                "scraper_user": user_email  # Also track which user was served this article
            }
            
            response = self.client.table(self.staging_table).update(update_data).eq("id", task_id).execute()
            
            if response.data and len(response.data) > 0:
                status_desc = "opened in window" if workflow_status == 1 else "extraction submitted"
                logger.info(f"Updated workflow status for task {task_id}: {workflow_status} ({status_desc})")
                return True
            else:
                logger.warning(f"No rows updated for workflow status on task {task_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating workflow status for task {task_id}: {e}")
            return False

    async def get_available_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        NEW RESTRICTIVE LOGIC WITH AI FALLBACK:
        1. Primary: Articles for specific clients (KFC/Databricks/Starface/WIP) + creator/unknown
        2. Fallback: Articles with focus_industry = "AI" + creator/unknown
        """
        try:
            # Apply server-side filters for new restrictive criteria
            response = (
                self.client
                .table(self.staging_table)
                .select(
                    "id, title, permalink_url, published_at, actor_name, source_title, source_url, "
                    "summary, content, subscription_source, source, client_priority, focus_industry, "
                    "headline_relevance, pub_tier, publication, clients, retry_count, dedupe_status, "
                    "WF_Pre_Check_Complete, WF_Extraction_Complete, wf_timestamp_claimed_at, WF_TIMESTAMP_Pre_Check_Complete, WF_Patch_Duplicate_Syndicate, next_retry_at, last_modified, created_at"
                )
                .eq("extraction_path", 2)
                .eq("dedupe_status", "original")
                .eq("WF_Pre_Check_Complete", True)
                .in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"])  # NEW: Only creator or unknown
                .order("created_at", desc=True)
                .limit(1000)
                .execute()
            )

            rows: List[Dict[str, Any]] = response.data or []

            # NEW TWO-TIER FILTERING: Primary (target clients) + Fallback (AI focus)
            primary_pool: List[Dict[str, Any]] = []
            fallback_pool: List[Dict[str, Any]] = []
            now = datetime.now(timezone.utc)
            target_clients = ["KFC", "Databricks", "Starface", "WIP"]
            
            for row in rows:
                wf_pre = row.get("WF_Pre_Check_Complete")
                wf_done = row.get("WF_Extraction_Complete")
                wf_claimed = row.get("wf_timestamp_claimed_at")
                wf_pre_ts = row.get("WF_TIMESTAMP_Pre_Check_Complete")
                wf_patch_duplicate = row.get("WF_Patch_Duplicate_Syndicate")
                clients_val = row.get("clients")
                focus_industry = row.get("focus_industry")
                
                # Basic eligibility checks
                pre_ok = (wf_pre is True) or (isinstance(wf_pre, str) and str(wf_pre).upper() == "TRUE")
                not_done = (wf_done is None) or (wf_done is False)
                not_claimed = (wf_claimed is None)  # Only unclaimed tasks
                dedupe_ok = str(row.get("dedupe_status") or "").strip().lower() == "original"
                valid_status = wf_patch_duplicate in ["creator", "unknown"]
                
                # Check 15-minute delay after pre-check completion
                pre_check_aged = True  # Default to True if no timestamp
                if wf_pre_ts:
                    try:
                        pre_check_time = datetime.fromisoformat(wf_pre_ts.replace('Z', '+00:00'))
                        pre_check_aged = (now - pre_check_time).total_seconds() >= 900  # 15 minutes = 900 seconds
                    except Exception:
                        # If timestamp parsing fails, default to allowing the article
                        pre_check_aged = True
                
                # Only proceed if basic criteria are met
                if not (pre_ok and not_done and not_claimed and dedupe_ok and pre_check_aged and valid_status):
                    continue
                
                # PRIMARY POOL: Check if clients contains any target keywords (case insensitive)
                has_target_client = False
                if clients_val:
                    clients_lower = str(clients_val).lower()
                    has_target_client = any(keyword.lower() in clients_lower for keyword in target_clients)
                
                if has_target_client:
                    primary_pool.append(row)
                    continue
                
                # FALLBACK POOL: Check if focus_industry is "AI"
                has_ai_focus = False
                if focus_industry:
                    if isinstance(focus_industry, list):
                        has_ai_focus = "AI" in focus_industry
                    else:
                        has_ai_focus = str(focus_industry).strip() == "AI"
                
                if has_ai_focus:
                    fallback_pool.append(row)
            
            # Use primary pool if available, otherwise fallback to AI pool
            if primary_pool:
                filtered = primary_pool
                logger.info(f"Using PRIMARY pool: {len(primary_pool)} target client articles")
            elif fallback_pool:
                filtered = fallback_pool
                logger.info(f"Using FALLBACK pool: {len(fallback_pool)} AI focus articles")
            else:
                filtered = []
                logger.info("No articles available in either primary or fallback pools")

            if filtered:
                # NEW SIMPLIFIED LOGIC: All articles meet target client criteria, so just randomize
                # Sort by created_at DESC first (newest first), then randomize to prevent race conditions
                def created_ts(row: Dict[str, Any]) -> float:
                    ts = row.get("created_at") or ""
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        return dt.timestamp()
                    except Exception:
                        return 0.0

                # Sort newest first, then randomize
                filtered_sorted = sorted(filtered, key=lambda row: -created_ts(row))
                
                pool_type = "PRIMARY (target clients)" if primary_pool else "FALLBACK (AI focus)"
                logger.info(
                    f"TWO-TIER LOGIC: {len(rows)} fetched, {len(filtered)} eligible from {pool_type} pool, returning top {limit}"
                )
                
                # Randomize to prevent race conditions when multiple users request simultaneously
                import random
                result = filtered_sorted[:limit]
                random.shuffle(result)  # Randomize the final selection
                return result
            else:
                logger.info("No available tasks found in either primary (target clients) or fallback (AI focus) pools")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching available tasks: {e}")
            return []

    async def availability_report(self, limit_fetch: int = 500) -> Dict[str, Any]:
        """
        Diagnostics: analyze why articles are excluded. Returns counts and samples by condition.
        """
        try:
            resp = (
                self.client
                .table(self.staging_table)
                .select(
                    "id, title, WF_Pre_Check_Complete, WF_Extraction_Complete, dedupe_status, extraction_path, created_at, clients, WF_Patch_Duplicate_Syndicate"
                )
                .eq("extraction_path", 2)
                .eq("WF_Pre_Check_Complete", True)
                .in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"])  # NEW: Only creator or unknown
                .order("created_at", desc=True)
                .limit(limit_fetch)
                .execute()
            )
            rows: List[Dict[str, Any]] = resp.data or []

            def is_pre_ok(v) -> bool:
                return (v is True) or (isinstance(v, str) and v.upper() == "TRUE")

            def is_not_done(v) -> bool:
                return (v is None) or (v is False)

            def is_original(v) -> bool:
                return str(v or "").strip().lower() == "original"

            total = len(rows)
            pre_ok = [r for r in rows if is_pre_ok(r.get("WF_Pre_Check_Complete"))]
            not_done = [r for r in rows if is_not_done(r.get("WF_Extraction_Complete"))]
            original = [r for r in rows if is_original(r.get("dedupe_status"))]

            passing_all = [
                r for r in rows
                if is_pre_ok(r.get("WF_Pre_Check_Complete"))
                and is_not_done(r.get("WF_Extraction_Complete"))
                and is_original(r.get("dedupe_status"))
            ]

            # Distribution helpers
            from collections import Counter
            dedupe_dist = Counter([str(r.get("dedupe_status") or "").strip() or "(empty)" for r in rows])
            pre_dist = Counter([
                "TRUE" if is_pre_ok(r.get("WF_Pre_Check_Complete")) else str(r.get("WF_Pre_Check_Complete"))
                for r in rows
            ])
            done_dist = Counter([
                "done" if not is_not_done(r.get("WF_Extraction_Complete")) else "not_done"
                for r in rows
            ])

            # Samples for quick inspection
            def ids(items: List[Dict[str, Any]], n: int = 10) -> List[str]:
                return [str(r.get("id")) for r in items[:n]]

            return {
                "success": True,
                "total_considered": total,
                "counts": {
                    "extraction_path_eq_2": total,
                    "pre_check_ok": len(pre_ok),
                    "not_completed": len(not_done),
                    "dedupe_original": len(original),
                    "passing_all": len(passing_all),
                },
                "distributions": {
                    "dedupe_status": dedupe_dist.most_common(),
                    "WF_Pre_Check_Complete": pre_dist.most_common(),
                    "WF_Extraction_Complete": done_dist.most_common(),
                },
                "samples": {
                    "passing_all_ids": ids(passing_all),
                    "failing_pre_check_ids": ids([r for r in rows if not is_pre_ok(r.get("WF_Pre_Check_Complete"))]),
                    "failing_not_done_ids": ids([r for r in rows if not is_not_done(r.get("WF_Extraction_Complete"))]),
                    "failing_dedupe_original_ids": ids([r for r in rows if not is_original(r.get("dedupe_status"))]),
                }
            }
        except Exception as e:
            logger.error(f"Error building availability report: {e}")
            return {"success": False, "error": str(e)}

    async def assign_task(self, task_id: str, scraper_id: str) -> bool:
        """
        Atomically claim a task by setting wf_timestamp_claimed_at
        Since we confirmed database is clean, assume success if no exception occurs
        """
        try:
            from datetime import datetime, timezone
            
            claim_timestamp = datetime.now(timezone.utc).isoformat()
            
            # Atomic update: claim the task only if it meets NEW RESTRICTIVE criteria
            response = (
                self.client
                .table(self.staging_table)
                .update({"wf_timestamp_claimed_at": claim_timestamp})
                .eq("id", task_id)
                .eq("extraction_path", 2)
                .eq("dedupe_status", "original")
                .eq("WF_Pre_Check_Complete", True)
                .in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"])  # NEW: Only creator or unknown
                .is_("wf_timestamp_claimed_at", "null")  # Only if unclaimed
                .neq("WF_Extraction_Complete", True)  # Exclude only completed tasks (TRUE)
                .execute()
            )
            
            # Verify the claim actually worked by checking if the record was updated
            # Also verify the article still meets target client criteria
            verify_response = (
                self.client
                .table(self.staging_table)
                .select("wf_timestamp_claimed_at, clients, WF_Patch_Duplicate_Syndicate, focus_industry")
                .eq("id", task_id)
                .single()
                .execute()
            )
            
            current_timestamp = verify_response.data.get("wf_timestamp_claimed_at") if verify_response.data else None
            clients_val = verify_response.data.get("clients") if verify_response.data else None
            patch_status = verify_response.data.get("WF_Patch_Duplicate_Syndicate") if verify_response.data else None
            focus_industry = verify_response.data.get("focus_industry") if verify_response.data else None
            
            # Verify article meets either PRIMARY (target clients) OR FALLBACK (AI focus) criteria
            target_clients = ["KFC", "Databricks", "Starface", "WIP"]
            
            # Check PRIMARY: target clients
            has_target_client = False
            if clients_val:
                clients_lower = str(clients_val).lower()
                has_target_client = any(keyword.lower() in clients_lower for keyword in target_clients)
            
            # Check FALLBACK: AI focus
            has_ai_focus = False
            if focus_industry:
                if isinstance(focus_industry, list):
                    has_ai_focus = "AI" in focus_industry
                else:
                    has_ai_focus = str(focus_industry).strip() == "AI"
            
            # Article must meet either primary OR fallback criteria
            meets_criteria = has_target_client or has_ai_focus
            criteria_type = "PRIMARY (target clients)" if has_target_client else ("FALLBACK (AI focus)" if has_ai_focus else "NONE")
            
            logger.info(f"Verification for task {task_id}: expected={claim_timestamp}, actual={current_timestamp}, clients={clients_val}, focus={focus_industry}, criteria={criteria_type}, status={patch_status}")
            
            # Check if the task was successfully claimed by verifying timestamp is set and meets criteria
            if (verify_response.data and current_timestamp is not None and meets_criteria and patch_status in ["creator", "unknown"]):
                # Parse both timestamps to compare them properly
                from datetime import datetime, timezone
                try:
                    # Parse the timestamp from the database
                    if isinstance(current_timestamp, str):
                        db_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
                    else:
                        db_time = current_timestamp
                    
                    # Parse our expected timestamp
                    our_time = datetime.fromisoformat(claim_timestamp.replace('Z', '+00:00'))
                    
                    # Check if timestamps are within 5 seconds (allowing for minor differences)
                    time_diff = abs((db_time - our_time).total_seconds())
                    if time_diff <= 5:
                        logger.info(f"Task {task_id} successfully claimed by scraper {scraper_id} (time_diff: {time_diff}s)")
                        return True
                    else:
                        logger.warning(f"Task {task_id} timestamp mismatch - time_diff: {time_diff}s")
                        return False
                except Exception as e:
                    logger.error(f"Error parsing timestamps for task {task_id}: {e}")
                    # Fallback: if we can't parse, but timestamp exists, assume success
                    logger.info(f"Task {task_id} claimed (timestamp exists, fallback success)")
                    return True
            else:
                logger.warning(f"Task {task_id} could not be claimed - verification failed (expected: {claim_timestamp}, got: {current_timestamp})")
                return False
                
        except Exception as e:
            logger.error(f"Error claiming task {task_id}: {e}")
            return False

    async def submit_extraction(self, task_id: str, scraper_id: str, extracted_data: Dict[str, Any], scraper_user: str = None) -> bool:
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
                "clients": original_article.get("clients"),  # Direct carryover ✅ - Fast Lane keywords
                "focus_industry": original_article.get("focus_industry"),  # Direct carryover ✅ - Industry prioritization
                "subscription": original_article.get("subscription"),  # Direct carryover ✅
                # "pub_tier": original_article.get("pub_tier"),  # REMOVED: Column doesn't exist in the_soups table
                "soup_dedupe_id": task_id,  # Links back to soup_dedupe.id ✅
                # Portal submit metadata for Recent-50 filtering
                "scraper_id": scraper_id,
                "scraper_user": scraper_user or scraper_id,  # User email goes into scraper_user field
                "submitted_at": current_time,
                # Optional timing info if provided by the UI
                "duration_sec": extracted_data.get("duration_sec")
            }
            
            logger.info(f"🗂️ Mapped soups_data (before cleanup): {soups_data}")
            
            # Remove None values for clean insertion
            soups_data = {k: v for k, v in soups_data.items() if v is not None}
            
            logger.info(f"🗂️ Final soups_data (after cleanup): {soups_data}")
            logger.info(f"📊 Inserting into table: {self.destination_table}")

            # Upsert fallback: perform SELECT → UPDATE or INSERT because the table
            # may not have a unique constraint on soup_dedupe_id (required by PostgREST upsert)
            existing = (
                self.client
                .table(self.destination_table)
                .select("soup_dedupe_id")
                .eq("soup_dedupe_id", task_id)
                .limit(1)
                .execute()
            )

            if existing.data:
                # Row exists → UPDATE it and stamp last_modified_at
                update_payload = {**soups_data}
                update_payload.pop("submitted_at", None)
                update_payload["last_modified_at"] = current_time
                write_response = (
                    self.client
                    .table(self.destination_table)
                    .update(update_payload)
                    .eq("soup_dedupe_id", task_id)
                    .execute()
                )
                logger.info(f"📤 Update response: {write_response}")
            else:
                # Row does not exist → INSERT new
                write_response = (
                    self.client
                    .table(self.destination_table)
                    .insert(soups_data)
                    .execute()
                )
                logger.info(f"📤 Insert response: {write_response}")

            if not write_response.data:
                logger.error(f"❌ Failed to write into {self.destination_table} - no data returned")
                logger.error(f"❌ Write response details: {write_response}")
                return False

            logger.info(f"✅ Successfully wrote into {self.destination_table}: {write_response.data}")
            
            # Update soup_dedupe status to completed
            update_data = {
                "extraction_path": 3,  # Mark as completed
                "WF_Extraction_Complete": True,
                "wf_timestamp_claimed_at": None,  # Reset claim on completion
                "last_modified": current_time
            }
            logger.info(f"🔄 Updating soup_dedupe with: {update_data}")
            
            # Double-guard: also set extraction_path=3 on completion to remove from queue
            update_response = self.client.table(self.staging_table).update({**update_data, "extraction_path": 3}).eq("id", task_id).execute()
            
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
            tb = traceback.format_exc()
            logger.error(f"💥 Full traceback: {tb}")
            # Propagate a descriptive error so the API can return a helpful message
            raise RuntimeError(f"submit_extraction failed: {type(e).__name__}: {str(e)}")

    async def get_recent_human(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch most recent human-portal submissions from the_soups."""
        try:
            # Grab a wider slice and sort in Python using our recency rule
            response = (
                self.client
                .table(self.destination_table)
                .select(
                    "soup_dedupe_id, Headline, Publication, Date, Story_Link, scraper_id, "
                    "submitted_at, created_at, last_modified_at"
                )
                .eq("scraper_id", "human_portal_user")
                .order("last_modified_at", desc=True)
                .limit(200)
                .execute()
            )

            rows: List[Dict[str, Any]] = response.data or []

            def recency_key(r: Dict[str, Any]):
                # Prefer last_modified_at, then submitted_at, then created_at
                return (
                    r.get("last_modified_at") or r.get("submitted_at") or r.get("created_at") or ""
                )

            rows_sorted = sorted(rows, key=recency_key, reverse=True)

            recent: List[Dict[str, Any]] = []
            for r in rows_sorted[:limit]:
                recent.append({
                    "id": r.get("soup_dedupe_id"),
                    "headline": r.get("Headline"),
                    "publication": r.get("Publication"),
                    "date": r.get("Date"),
                    "story_link": r.get("Story_Link"),
                    "submitted_at": r.get("submitted_at"),
                    "created_at": r.get("created_at"),
                    "last_modified_at": r.get("last_modified_at")
                })

            return recent
        except Exception as e:
            logger.error(f"Error fetching recent human submissions: {e}")
            return []

    async def handle_failure(self, task_id: str, scraper_id: str, error_message: str, scraper_user: str = None) -> bool:
        """
        Handle extraction failure by marking as complete (unable to extract)
        This removes the article from the available queue
        """
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Mark as extraction complete (even though failed) to remove from queue
            # Use columns that exist in the current schema (fallback from missing WF_Extraction_Complete_Explanation)
            update_data = {
                "WF_Extraction_Complete": True,  # Mark as processed/complete
                "wf_timestamp_claimed_at": None,  # Reset claim on failure
                "wf_extraction_failure": error_message,  # Capture rejection reason (existing column)
                "wf_timestamp_extraction_failure": current_time,  # Failure timestamp
                "last_modified": current_time,
                "WF_TIMESTAMP_Extraction_Complete": current_time,  # Set completion timestamp
            }
            
            # Add scraper_user if available (should work in soup_dedupe table)
            if scraper_user:
                update_data["scraper_user"] = scraper_user
            
            # Try to increment retry_count if it exists
            try:
                response = self.client.table(self.staging_table).select("retry_count").eq("id", task_id).execute()
                if response.data and len(response.data) > 0:
                    current_retry_count = response.data[0].get("retry_count", 0)
                    update_data["retry_count"] = current_retry_count + 1
            except Exception as e:
                logger.warning(f"Could not update retry_count for {task_id}: {e}")
            
            # Double-guard: also set extraction_path=3 to remove from queue
            update_response = self.client.table(self.staging_table).update({**update_data, "extraction_path": 3}).eq("id", task_id).execute()
            
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

    async def get_soups_by_soup_dedupe_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load a the_soups row by soup_dedupe_id and map to article-like shape."""
        try:
            response = (
                self.client
                .table(self.destination_table)
                .select("*")
                .eq("soup_dedupe_id", task_id)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            row = response.data[0]
            # Map to staging-like keys expected by the UI
            mapped = {
                "id": row.get("soup_dedupe_id"),
                "title": row.get("Headline"),
                "publication": row.get("Publication"),
                "actor_name": row.get("Author"),
                "published_at": row.get("Date"),
                "permalink_url": row.get("Story_Link"),
                "clients": row.get("clients"),
                "focus_industry": row.get("focus_industry"),
            }
            return mapped
        except Exception as e:
            logger.error(f"Error fetching the_soups by soup_dedupe_id {task_id}: {e}")
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
        """
        Release tasks that have been claimed but not completed within timeout
        Uses wf_timestamp_claimed_at to find expired tasks
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            # Calculate cutoff time (tasks claimed before this are expired)
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            cutoff_iso = cutoff_time.isoformat()
            
            # First, get count of tasks that match our NEW RESTRICTIVE criteria (for logging)
            count_response = (
                self.client
                .table(self.staging_table)
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
            
            released_count = count_response.count or 0
            
            if released_count > 0:
                # Release the expired tasks by setting wf_timestamp_claimed_at to NULL (NEW RESTRICTIVE criteria)
                response = (
                    self.client
                    .table(self.staging_table)
                    .update({"wf_timestamp_claimed_at": None})  # Release the claim
                    .eq("extraction_path", 2)
                    .eq("dedupe_status", "original")
                    .eq("WF_Pre_Check_Complete", True)
                    .in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"])  # NEW: Only creator or unknown
                    .is_("WF_Extraction_Complete", "null")
                    .not_.is_("wf_timestamp_claimed_at", "null")  # Must be claimed
                    .lt("wf_timestamp_claimed_at", cutoff_iso)    # Claimed before cutoff
                    .execute()
                )
                
                logger.info(f"Released {released_count} expired tasks (claimed > {timeout_minutes} minutes ago)")
            
            return released_count
            
        except Exception as e:
            logger.error(f"Error releasing expired tasks: {e}")
            return 0

    # ===================== Admin Metrics =====================
    async def metrics_human_per_day(self, days: int = 14) -> List[Dict[str, Any]]:
        """Counts of human-portal submissions per day for the last N days."""
        try:
            # Pull recent rows and group by date in Python
            resp = (
                self.client
                .table(self.destination_table)
                .select("submitted_at, created_at, last_modified_at")
                .eq("scraper_id", "human_portal_user")
                .order("last_modified_at", desc=True)
                .limit(1000)
                .execute()
            )
            rows = resp.data or []
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=days)
            buckets: Dict[str, int] = {}
            for r in rows:
                ts = r.get("last_modified_at") or r.get("submitted_at") or r.get("created_at")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
                if dt < cutoff:
                    continue
                dstr = dt.date().isoformat()
                buckets[dstr] = buckets.get(dstr, 0) + 1
            # Return sorted by date asc
            return [{"date": k, "count": buckets[k]} for k in sorted(buckets.keys())]
        except Exception as e:
            logger.error(f"metrics_human_per_day error: {e}")
            return []

    async def metrics_soups_groupings(self) -> Dict[str, List[Dict[str, Any]]]:
        """Counts in the_soups grouped by clients and focus_industry."""
        try:
            resp = (
                self.client
                .table(self.destination_table)
                .select("clients, focus_industry")
                .limit(5000)
                .execute()
            )
            rows = resp.data or []
            by_clients: Dict[str, int] = {}
            by_focus: Dict[str, int] = {}
            for r in rows:
                c = (r.get("clients") or "Unspecified").strip()
                if not c:
                    c = "Unspecified"
                by_clients[c] = by_clients.get(c, 0) + 1
                fi = r.get("focus_industry")
                if isinstance(fi, list):
                    for v in fi:
                        val = (str(v) or "Unspecified").strip() or "Unspecified"
                        by_focus[val] = by_focus.get(val, 0) + 1
                elif fi is not None:
                    val = (str(fi) or "Unspecified").strip() or "Unspecified"
                    by_focus[val] = by_focus.get(val, 0) + 1
            return {
                "by_clients": sorted([{"key": k, "count": v} for k, v in by_clients.items()], key=lambda x: x["count"], reverse=True),
                "by_focus_industry": sorted([{"key": k, "count": v} for k, v in by_focus.items()], key=lambda x: x["count"], reverse=True)
            }
        except Exception as e:
            logger.error(f"metrics_soups_groupings error: {e}")
            return {"by_clients": [], "by_focus_industry": []}

    async def metrics_pending_groupings(self) -> Dict[str, List[Dict[str, Any]]]:
        """Counts of pending (awaiting scrape) grouped by clients and focus_industry from soup_dedupe."""
        try:
            # Fetch superset with NEW RESTRICTIVE criteria
            resp = self.client.table(self.staging_table).select(
                "id, clients, focus_industry, WF_Pre_Check_Complete, WF_Extraction_Complete, extraction_path, created_at, WF_TIMESTAMP_Pre_Check_Complete, WF_Patch_Duplicate_Syndicate"
            ).eq("extraction_path", 2).eq("WF_Pre_Check_Complete", True).in_("WF_Patch_Duplicate_Syndicate", ["creator", "unknown"]).limit(4000).execute()
            rows = resp.data or []
            filtered: List[Dict[str, Any]] = []
            target_clients = ["KFC", "Databricks", "Starface", "WIP"]
            for row in rows:
                wf_pre = row.get("WF_Pre_Check_Complete")
                wf_done = row.get("WF_Extraction_Complete")
                wf_patch_duplicate = row.get("WF_Patch_Duplicate_Syndicate")
                clients_val = row.get("clients")
                
                pre_ok = (wf_pre is True) or (isinstance(wf_pre, str) and wf_pre.upper() == "TRUE")
                not_done = (wf_done is None) or (wf_done is False)
                valid_status = wf_patch_duplicate in ["creator", "unknown"]
                
                # NEW: Check if clients contains any target keywords (case insensitive)
                has_target_client = False
                if clients_val:
                    clients_lower = str(clients_val).lower()
                    has_target_client = any(keyword.lower() in clients_lower for keyword in target_clients)
                
                if pre_ok and not_done and valid_status and has_target_client:
                    filtered.append(row)
            by_clients: Dict[str, int] = {}
            by_focus: Dict[str, int] = {}
            for r in filtered:
                c = (r.get("clients") or "Unspecified").strip()
                if not c:
                    c = "Unspecified"
                by_clients[c] = by_clients.get(c, 0) + 1
                fi = r.get("focus_industry")
                if isinstance(fi, list):
                    for v in fi:
                        val = (str(v) or "Unspecified").strip() or "Unspecified"
                        by_focus[val] = by_focus.get(val, 0) + 1
                elif fi is not None:
                    val = (str(fi) or "Unspecified").strip() or "Unspecified"
                    by_focus[val] = by_focus.get(val, 0) + 1
            return {
                "by_clients": sorted([{"key": k, "count": v} for k, v in by_clients.items()], key=lambda x: x["count"], reverse=True),
                "by_focus_industry": sorted([{"key": k, "count": v} for k, v in by_focus.items()], key=lambda x: x["count"], reverse=True)
            }
        except Exception as e:
            logger.error(f"metrics_pending_groupings error: {e}")
            return {"by_clients": [], "by_focus_industry": []}

    async def metrics_served_articles(self) -> Dict[str, Any]:
        """
        Get Articles Served and Duplicates Served metrics for last 24h and 3h
        
        Articles Served: scraper_user has a value (not null)
        Duplicates Served: WF_Routing_Verified = True AND WF_Pre_Check_Complete = False AND scraper_user has a value
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            now = datetime.now(timezone.utc)
            cutoff_24h = now - timedelta(hours=24)
            cutoff_3h = now - timedelta(hours=3)
            
            # Query soup_dedupe for served articles (scraper_user is not null)
            # Get articles with timestamps in the last 24 hours
            response = (
                self.client
                .table(self.staging_table)
                .select("id, scraper_user, WF_Routing_Verified, WF_Pre_Check_Complete, WF_TIMESTAMP_served_human_scrape, created_at")
                .not_.is_("scraper_user", "null")  # Articles served (scraper_user has value)
                .gte("WF_TIMESTAMP_served_human_scrape", cutoff_24h.isoformat())  # Last 24 hours
                .execute()
            )
            
            rows = response.data or []
            
            # Count articles served
            articles_24h = 0
            articles_3h = 0
            
            # Count duplicates served
            duplicates_24h = 0
            duplicates_3h = 0
            
            for row in rows:
                served_timestamp = row.get("WF_TIMESTAMP_served_human_scrape")
                if not served_timestamp:
                    continue
                    
                try:
                    served_dt = datetime.fromisoformat(served_timestamp.replace('Z', '+00:00'))
                except Exception:
                    continue
                
                # Count articles served
                if served_dt >= cutoff_24h:
                    articles_24h += 1
                if served_dt >= cutoff_3h:
                    articles_3h += 1
                
                # Check if it's a duplicate (WF_Routing_Verified=True AND WF_Pre_Check_Complete=False)
                is_duplicate = (
                    row.get("WF_Routing_Verified") is True and 
                    row.get("WF_Pre_Check_Complete") is False
                )
                
                if is_duplicate:
                    if served_dt >= cutoff_24h:
                        duplicates_24h += 1
                    if served_dt >= cutoff_3h:
                        duplicates_3h += 1
            
            return {
                "articles_served": {
                    "last_24_hours": articles_24h,
                    "last_3_hours": articles_3h
                },
                "duplicates_served": {
                    "last_24_hours": duplicates_24h,
                    "last_3_hours": duplicates_3h
                },
                "timestamp": now.isoformat(),
                "cutoff_24h": cutoff_24h.isoformat(),
                "cutoff_3h": cutoff_3h.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting served metrics: {e}")
            return {
                "articles_served": {
                    "last_24_hours": 0,
                    "last_3_hours": 0
                },
                "duplicates_served": {
                    "last_24_hours": 0,
                    "last_3_hours": 0
                },
                "error": str(e)
            }

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