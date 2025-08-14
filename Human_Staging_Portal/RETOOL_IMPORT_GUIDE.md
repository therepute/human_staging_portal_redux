# 🚀 Retool Import Guide - Complete Dual-Window Scraper

## Quick Import Method

### 📁 **Import the Complete App Configuration**

1. **In Retool, go to:** `Apps` → `Create new` → `Import app`

2. **Upload:** `retool_app_config.json` (from this directory)

3. **Configure Resource:** Make sure `staging_portal_human_scraper` resource is available

4. **Test Connection:** Verify your API server is running at `http://localhost:8001`

---

## 🎯 **What This Builds Automatically**

### **Complete Dual-Window Interface:**
- ✅ **Left Panel:** Task assignment with branded orange buttons
- ✅ **Right Panel:** Content extraction form with all fields
- ✅ **Header Stats:** Real-time system health and queue status
- ✅ **Brand Styling:** Full ReputeAI color palette implementation
- ✅ **Automatic Workflows:** Task assignment → Article opening → Content extraction → Submission

### **6 Pre-configured API Queries:**
1. **`health_check`** - System monitoring (auto-refresh every 30s)
2. **`get_next_task`** - Priority-based task assignment
3. **`submit_task`** - Content submission with extracted data
4. **`fail_task`** - Failure handling with reason codes
5. **`queue_status`** - Queue monitoring (auto-refresh every 15s)
6. **`scraper_tasks`** - Individual scraper performance tracking

### **Interactive Components:**
- 🎯 **Get Next Task** button (auto-opens article in new tab)
- 📝 **Content Extraction Form** with 9 structured fields
- ✅ **Submit Success** button (saves and clears form)
- ❌ **Mark Failed** button (opens failure modal)
- 📊 **Real-time Dashboard** metrics

---

## 🔧 **Manual Configuration (If Import Fails)**

### Step 1: Create Blank App
```
Apps → Create new → Blank app → Name: "Human Staging Portal"
```

### Step 2: Add Your Resource
```
Bottom panel → New + → Select: staging_portal_human_scraper
```

### Step 3: Copy Queries from JSON
Use the `queries` section from `retool_app_config.json`:

#### Health Check Query:
- **Name:** `health_check`
- **Method:** `GET`
- **URL Path:** `/api/health`
- **Auto-refresh:** `30000ms`
- **Run on load:** ✅

#### Get Next Task Query:
- **Name:** `get_next_task`
- **Method:** `GET` 
- **URL Path:** `/api/tasks/next`
- **Parameters:** `scraper_id = {{ scraper_id.value }}`

#### Submit Task Query:
- **Name:** `submit_task`
- **Method:** `POST`
- **URL Path:** `/api/tasks/submit`
- **Headers:** `Content-Type: application/json`
- **Body:** *(Copy from JSON config)*

### Step 4: Add Components
Copy the entire `components` section from the JSON file

### Step 5: Add Custom CSS
Copy the `css` section for brand styling

---

## 🎨 **Brand Features Included**

### **Color Palette Implementation:**
- **Primary Orange:** `#fc5f36` (buttons, links, highlights)
- **Deep Navy:** `#2C3E50` (header gradient background)
- **Dark Blue:** `#1c2d50` (main brand color)
- **Success Green:** `#7FB069` (submit buttons)
- **Error Coral:** `#C85450` (failure buttons)
- **Warm Beige:** `#E8D5B7` (task display background)

### **Interactive Elements:**
- Gradient backgrounds with brand colors
- Hover effects with shadow animations
- Focus states with orange accent border
- Glass-effect containers with backdrop blur
- Brand-consistent button styling

---

## 📋 **Workflow Features**

### **Automatic Task Management:**
1. **Click "Get Next Task"** → API assigns priority task
2. **Article auto-opens** in new tab (dual-window setup)
3. **Extract content** in Retool form while reading article
4. **Submit** → Saves to database, clears form, refreshes queue
5. **Repeat** for next task

### **Failure Handling:**
- **Mark Failed** → Opens modal with reason selection
- **Predefined reasons:** Not accessible, Paywall, Technical error, etc.
- **Optional notes** field for additional context
- **Auto-retry logic** with exponential backoff

### **Real-time Monitoring:**
- **System health** indicator (green/red status)
- **Available tasks** counter (updates every 30s)
- **Queue composition** by priority sources
- **Extraction duration** tracking

---

## 🧪 **Testing Your Import**

### Test Sequence:
1. **Check Health:** Top stats should show "healthy" and task count
2. **Get Task:** Button should assign task and open article URL
3. **Form Fields:** All 9 extraction fields should be visible
4. **Submit Test:** Fill minimal data and test submission
5. **Failure Test:** Test failure modal and reason selection

### Expected Results:
- ✅ Orange branded buttons and styling
- ✅ Real-time dashboard updates
- ✅ Automatic article opening in new tab
- ✅ Form submission clearing and task reassignment
- ✅ Queue status updates after each action

---

## 🚨 **Troubleshooting**

### **Import Issues:**
- **Resource not found:** Ensure `staging_portal_human_scraper` exists
- **JSON parsing error:** Validate JSON syntax
- **Component errors:** Check Retool component name compatibility

### **Runtime Issues:**
- **API connection failed:** Verify server running on `localhost:8001`
- **CORS errors:** Server has CORS enabled for Retool
- **Query timeouts:** Check network connectivity

### **Quick Fix Commands:**
```bash
# Restart API server
cd Human_Staging_Portal
export SUPABASE_URL=https://nuumgwdbiifwsurioavm.supabase.co
export SUPABASE_ANON_KEY="your_key_here"
python main_api.py

# Test endpoints
curl http://localhost:8001/api/health
curl "http://localhost:8001/api/tasks/next?scraper_id=test"
```

---

## 📊 **Performance Features**

### **Optimized for Production:**
- **Auto-refresh intervals:** Health (30s), Queue (15s)
- **Unique scraper IDs:** Prevents task conflicts
- **Local storage:** Persistent scraper identity
- **Background maintenance:** Automatic expired task cleanup
- **Priority queuing:** Client priority → Publication tier → Time factors

### **Scalability Features:**
- **Multi-scraper support:** Each user gets unique ID
- **Domain cooldowns:** Publisher-specific safety rules
- **Retry logic:** Automatic failure recovery
- **Task timeouts:** 30-minute automatic release

---

## 🎉 **Ready to Use!**

After import, your Retool app will be a production-ready dual-window scraper with:
- **Professional ReputeAI branding**
- **Complete API integration** 
- **Real-time monitoring**
- **Failure recovery**
- **Performance optimization**

**Total setup time:** ~5 minutes with JSON import vs. ~2+ hours manual building! 