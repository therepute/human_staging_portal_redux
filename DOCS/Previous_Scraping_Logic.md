# Previous Scraping Logic Documentation

**Implementation Period:** September 11 - September 22, 2025
**Context:** Logic implemented to accommodate Tadesse's Pink Code patch and prevent race conditions

## Current Scraper Eligibility Criteria

### Server-Side Filters (Applied in Supabase Query)
All articles must meet ALL of the following criteria to be fetched from the database:

1. **`extraction_path = 2`** - Only articles designated for human extraction
2. **`dedupe_status = "original"`** - Only original articles, not duplicates
3. **`WF_Pre_Check_Complete = True`** - MANDATORY: Article must have completed pre-check validation
4. **`WF_Patch_Duplicate_Syndicate != "suppressed"`** - Exclude articles marked as suppressed duplicates
5. **`ORDER BY created_at DESC`** - Newest articles first (within priority groups)
6. **`LIMIT 1000`** - Fetch up to 1000 eligible articles for prioritization

### Client-Side Post-Filters (Applied after database fetch)
Additional safety checks applied to each article:

1. **Pre-Check Validation:**
   - `WF_Pre_Check_Complete = True` (string "TRUE" also accepted)

2. **Extraction Status Check:**
   - `WF_Extraction_Complete != True` (allows NULL and FALSE values)
   - NULL = Article not yet attempted
   - FALSE = Article attempted but failed, can retry
   - TRUE = Article completed, exclude from scraping

3. **Claim Status:**
   - `wf_timestamp_claimed_at IS NULL` - Only unclaimed articles

4. **Dedupe Status Double-Check:**
   - `dedupe_status = "original"` (case-insensitive)

5. **Suppression Check:**
   - `WF_Patch_Duplicate_Syndicate != "suppressed"`

6. **15-Minute Pre-Check Delay:**
   - Articles must be at least 15 minutes older than their `WF_TIMESTAMP_Pre_Check_Complete`
   - Prevents conflicts during dedupe processing
   - Default to eligible if timestamp parsing fails

## Prioritization System (Applied to Eligible Articles)

Articles are sorted into priority tiers, with newest first within each tier:

### 1. 🚀 Fast Lane (Priority 0)
- **Criteria:** `clients` field contains any of: "databricks", "starface", "bombas", "wip", "kfc"
- **Sorting:** `created_at DESC` (newest first)

### 2. 👥 Regular Clients (Priority 1)
- **Criteria:** `clients` field has value (not NULL, empty, or "unspecified")
- **Sorting:** `created_at DESC` (newest first)

### 3. ⭐ Client Priority (Priority 2)
- **Criteria:** `client_priority > 0`
- **Sorting:** Higher `client_priority` first, then `created_at DESC`

### 4. 🎯 Focus Industry (Priority 3)
- **Criteria:** `focus_industry` field has value (not NULL or empty)
- **Sorting:** `created_at DESC` (newest first)

### 5. 📰 Everything Else (Priority 4)
- **Criteria:** All other eligible articles
- **Sorting:** `created_at DESC` (newest first)

## Race Condition Prevention

### Randomization
- After prioritization and limiting to top 50 articles, the final list is **randomized**
- Ensures different users get different initial task orders
- Prevents multiple users from claiming the same first task simultaneously

### Atomic Claiming Logic
When a user attempts to claim a task, the system:

1. **Atomic Update:** Sets `wf_timestamp_claimed_at` only if ALL conditions are still met:
   - `id = task_id`
   - `extraction_path = 2`
   - `dedupe_status = "original"`
   - `WF_Pre_Check_Complete = True`
   - `WF_Patch_Duplicate_Syndicate != "suppressed"`
   - `wf_timestamp_claimed_at IS NULL`
   - `WF_Extraction_Complete != True`

2. **Verification:** Reads back the record to confirm the claim timestamp was set
3. **Timestamp Validation:** Ensures the returned timestamp matches the expected claim time
4. **Success Confirmation:** Only returns `True` if verification passes

## Database Schema Fields Referenced

### soup_dedupe Table Fields:
- `id` - Unique article identifier
- `extraction_path` - Processing path (2 = human extraction)
- `dedupe_status` - "original" vs duplicate status
- `WF_Pre_Check_Complete` - Boolean: pre-check validation completed
- `WF_Extraction_Complete` - Boolean: extraction completed (NULL/FALSE/TRUE)
- `WF_Patch_Duplicate_Syndicate` - String: suppression status
- `wf_timestamp_claimed_at` - Timestamp: when article was claimed
- `WF_TIMESTAMP_Pre_Check_Complete` - Timestamp: when pre-check completed
- `clients` - String: client assignments
- `client_priority` - Integer: priority level
- `focus_industry` - Array/String: industry focus
- `created_at` - Timestamp: article creation

## Key Implementation Notes

1. **Server-side filtering is primary** - Reduces database load and ensures consistency
2. **Client-side filtering is safety net** - Handles edge cases and timing issues
3. **15-minute delay prevents dedupe conflicts** - Allows Pink Code patch processing to complete
4. **Randomization reduces race conditions** - Multiple users get different task orders
5. **Atomic claiming with verification** - Prevents duplicate assignments
6. **Inclusive extraction status logic** - Allows retry of failed extractions (FALSE values)

## Files Implementing This Logic

- **Primary:** `Human_Staging_Portal/utils/database_connector.py`
  - `get_available_tasks()` method (lines 140-275)
  - `assign_task()` method (lines 360-420)
- **Supporting:** `Human_Staging_Portal/main_api.py`
  - API endpoints that use the database connector

---

*This documentation preserves the exact scraper logic implemented between 9/11-9/22/2025 for potential reversion if needed.*
