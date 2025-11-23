# Human Staging Portal 🚀

The Human Staging Portal is Component 2 of ReputeAI's content extraction system, designed to manage human scrapers for articles that require manual extraction.

## Overview

This portal receives filtered articles from the DeDupe System where `extraction_path = 2` and manages human scrapers through a dual-window Retool interface:
- **Task Management Portal**: Assigns priority-based tasks to scrapers
- **Article Browser**: Separate tab/window for scrapers to view and extract content

## 🏗️ Architecture

```
DeDupe System (Soup_Dedupe table)
    ↓ extraction_path = 2 & WF_Pre_Check_Complete = True
Human Staging Portal (FastAPI Backend)
    ↓ Extracted content + metadata  
The_Soups (Destination table)
```

## 📊 Database Integration

### Input Source: `Soup_Dedupe` Table
- **Filter Criteria**: `extraction_path = 2` AND `WF_Pre_Check_Complete = True/TRUE` AND `status = 'pending'`
- **Priority Ordering**: `client_priority DESC, created_at DESC`

### Output Destination: `the_soups` Table
- **Content Mapping**: Maps extracted data to final schema
- **Metadata**: Preserves priority, source, and timing information

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Ensure environment variables are set (already configured)
SUPABASE_URL=https://nuumgwdbiifwsurioavm.supabase.co
SUPABASE_ANON_KEY=<your_key>
```

### 2. Install Dependencies
```bash
cd Human_Staging_Portal
pip install -r requirements.txt
```

### 3. Test Connection
```bash
SUPABASE_URL=https://nuumgwdbiifwsurioavm.supabase.co SUPABASE_ANON_KEY="<your_key>" python test_connection.py
```

### 4. Start API Server
```bash
python start_portal.py
```

The server will start on `http://localhost:8001`

## 📋 API Endpoints

### Core Task Management
- `GET /api/tasks/next?scraper_id=<id>` - Get next highest priority task
- `POST /api/tasks/submit` - Submit extracted content
- `POST /api/tasks/fail` - Mark task as failed with error details

### Monitoring & Management
- `GET /api/health` - System health check with task count
- `GET /api/tasks/available?limit=10` - View available tasks
- `GET /api/tasks/{task_id}` - Get specific task details
- `GET /api/scrapers/{scraper_id}/tasks` - Get scraper's assigned tasks

### Maintenance
- `POST /api/maintenance/release-expired?timeout_minutes=30` - Release expired tasks

## 🎯 Priority System

Tasks are automatically prioritized using a multi-factor scoring system:

### Priority Levels
- **URGENT (1500+ pts)**: Client alerts from tier 1 publications
- **HIGH (1000+ pts)**: Client content or breaking news  
- **STANDARD (500+ pts)**: Regular relevant content
- **LOW (<500 pts)**: Background content

### Scoring Factors
- **Client Priority**: 1000 base points for client articles
- **Source Priority**: 500 base points for high-value sources
- **Publication Tier**: 50-400 points based on tier (1=highest)
- **Time Factors**: Bonus for urgent (<2hrs), penalty for old (>24hrs)
- **Headline Relevance**: 0-100 points based on relevance score
- **Retry Penalty**: -50 points per retry attempt

## 🔒 Domain Safety

Publisher-specific cooldown rules prevent overloading:

- **WSJ**: 3 minutes, 1 concurrent
- **NYT**: 2 minutes, 2 concurrent  
- **Reuters/Bloomberg**: 90 seconds, 2 concurrent
- **CNN/BBC**: 30 seconds, 2 concurrent
- **TechCrunch**: 20 seconds, 3 concurrent
- **Default**: 60 seconds, 3 concurrent

## 📱 Retool Integration

### Task Assignment Flow
1. Scraper requests next task via Retool interface
2. API assigns highest priority available task
3. Task locked to scraper with timeout (30 min default)
4. Scraper opens article URL in separate browser tab
5. Scraper extracts content and submits via Retool form

### Required Retool Components
- **Task Request Button**: Calls `/api/tasks/next`
- **Task Display Panel**: Shows title, URL, priority info
- **Content Form**: Fields for headline, author, body, publication
- **Submit/Fail Buttons**: Submit extraction or mark failed

## 🔧 Configuration

### Key Settings (`config/portal_config.yaml`)
- **Task Assignment**: Max 5 concurrent per scraper, 30min timeout
- **Priority Refresh**: Every 5 minutes
- **Domain Rules**: Publisher-specific cooldowns
- **API Settings**: CORS enabled for Retool integration

## 🔐 Security Best Practices

### Environment Variables
- **NEVER** commit `.env` files to version control
- Use `.env.example` as a template for required variables
- Store sensitive credentials in environment variables or secure secret management services

### Subscription Credentials
- **NEVER** commit `login_credentials.yaml` or similar credential files to git
- Store credentials in one of these secure locations:
  - **Option A**: Encrypted database table with restricted access
  - **Option B**: Secure file storage outside the repository (not in git)
  - **Option C**: Secret management service (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate credentials immediately if accidentally exposed
- Use `.gitignore` to prevent accidental commits

### Deployment Security
- Use strong, randomly generated `SESSION_SECRET_KEY` (generate with `secrets.token_urlsafe(32)`)
- Enable HTTPS in production (Railway provides this automatically)
- Restrict database access to application IPs only
- Use read-only database credentials where possible
- Enable audit logging for sensitive operations
- Regularly review and rotate API keys

### Credential Rotation
If credentials are exposed:
1. Immediately rotate all affected passwords
2. Review access logs for unauthorized usage
3. Purge sensitive data from git history using `git filter-branch` or `BFG Repo-Cleaner`
4. Notify stakeholders about potential exposure
5. Update security policies to prevent recurrence

## 📊 Monitoring

### Health Check Response
```json
{
  "status": "healthy",
  "tasks_available": 10,
  "system_health": "operational"
}
```

### Available Tasks Response
```json
{
  "success": true,
  "count": 10,
  "tasks": [
    {
      "id": "GA_20250716_062709_000001",
      "title": "CreditBank PNG And Entrust Aim To Enable...",
      "client_priority": 1,
      "pub_tier": 4,
      "source": "Google Alert",
      "permalink_url": "https://..."
    }
  ]
}
```

## 🔄 Task Lifecycle

1. **Available**: `extraction_path=2`, `status=pending`, `WF_Pre_Check_Complete=True`
2. **Assigned**: Task assigned to scraper with `assigned_at` timestamp
3. **Completed**: Content extracted and saved to `the_soups` table
4. **Failed**: Marked failed with retry logic (max 3 attempts)
5. **Expired**: Auto-released if not completed within timeout

## 🛠️ Development

### Testing
```bash
# Test database connection
python test_connection.py

# Start development server with auto-reload
python main_api.py

# Manual API testing
curl http://localhost:8001/api/health
```

### File Structure
```
Human_Staging_Portal/
├── config/
│   └── portal_config.yaml      # System configuration
├── utils/
│   └── database_connector.py   # Supabase integration
├── main_api.py                 # FastAPI server
├── start_portal.py            # Startup script
├── test_connection.py         # Connection tester
├── requirements.txt           # Dependencies
├── .env                      # Environment variables
└── README.md                 # This file
```

## 📈 Current Status

✅ **Backend Complete**: All 8 API endpoints functional  
✅ **Database Integration**: Connected to Soup_Dedupe and the_soups  
✅ **Priority System**: Multi-factor scoring implemented  
✅ **Domain Safety**: Publisher cooldowns configured  
✅ **Task Management**: Assignment, submission, failure handling  
✅ **Connection Verified**: 10 articles found ready for extraction  

🔄 **Next Step**: Build Retool interface for dual-window scraper workflow

## 🆘 Troubleshooting

### Common Issues

1. **No tasks available**: Check that articles have `extraction_path=2` and `WF_Pre_Check_Complete=True`
2. **Database connection failed**: Verify SUPABASE_URL and SUPABASE_ANON_KEY
3. **Task assignment failed**: May be taken by another scraper, try again
4. **Expired tasks**: Use `/api/maintenance/release-expired` to free stuck tasks

### Log Files
- **API Logs**: Console output during development
- **Database Logs**: Automatic HTTP request logging
- **Error Logs**: Exception details with stack traces

## 🔗 Integration Points

- **Input**: DeDupe System → Soup_Dedupe table
- **Output**: Human Portal → the_soups table  
- **Interface**: Retool dual-window system
- **Monitoring**: FastAPI endpoints for system health

## Deploy

This repo includes a `Procfile` with the start command:

```
web: uvicorn main_api:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` as environment variables on your platform. The app root for deployment is the `Human_Staging_Portal/` subdirectory.

---

**Human Staging Portal v1.0** - Ready for Retool interface development 🎯 