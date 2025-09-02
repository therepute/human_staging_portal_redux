## Human Portal Queue — How It Works and How To Query It

This doc explains the queue eligibility rules used by the Human Staging Portal, how to reproduce the total eligible count in SQL, and example filters by clients, client_priority, and focus_industry.

### Eligibility (what shows up in the queue)

An article is eligible for the portal queue when ALL of the following are true:

- extraction_path = 2
- "WF_Extraction_Complete" is NULL or FALSE
- dedupe_status = 'original'
- "WF_Pre_Check_Complete" = TRUE

Notes
- Quoted identifiers are required for the WF_* fields because they are defined with quotes in the schema.
- The UI also enforces these conditions when fetching tasks.

### Prioritization (ordering within the queue)

After building the eligible set, the portal orders items as follows:
1) clients present → newest created_at first
2) client_priority > 0 → higher client_priority first, then newest created_at
3) focus_industry present → newest created_at first
4) everything else → newest created_at first

This ordering is applied in-app after fetching a large, recent slice from the database.

### SQL — total number of eligible (portal queue count)

```sql
SELECT COUNT(*) AS portal_queue_count
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE;
```

### SQL — sample newest eligible rows

```sql
SELECT id, title, publication, created_at
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
ORDER BY created_at DESC
LIMIT 50;
```

### Filters inside the eligible set

All filters below assume the base eligibility WHERE clause above; append these predicates as needed.

#### A) “clients in queue”

Count with any non-empty, non-"Unspecified" clients value:
```sql
SELECT COUNT(*) AS with_clients
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients IS NOT NULL
  AND btrim(clients) <> ''
  AND lower(clients) <> 'unspecified';
```

Example: restrict to one client keyword (ILIKE, case-insensitive):
```sql
-- rows for clients containing 'Meta'
SELECT id, title, clients, created_at
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%Meta%'
ORDER BY created_at DESC
LIMIT 100;
```

#### B) “client_priority in queue”

Count with client_priority > 0:
```sql
SELECT COUNT(*) AS with_priority
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND COALESCE(client_priority, 0) > 0;
```

Example: list highest-priority first:
```sql
SELECT id, title, client_priority, created_at
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND COALESCE(client_priority, 0) > 0
ORDER BY client_priority DESC, created_at DESC
LIMIT 100;
```

#### C) “focus_industry in queue”

Count with any non-empty focus_industry array:
```sql
SELECT COUNT(*) AS with_focus
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND COALESCE(cardinality(focus_industry), 0) > 0;
```

Example: restrict to a specific industry value (e.g., 'AI'):
```sql
SELECT id, title, focus_industry, created_at
FROM public.soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND 'AI' = ANY(focus_industry)
ORDER BY created_at DESC
LIMIT 100;
```

### API helpers (optional)

- GET /api/tasks/available?limit=50
  - Returns a recent slice of eligible rows after app-side prioritization
- GET /api/tasks/next
  - Returns the next assigned task, or 404 if none
- GET /api/tasks/availability_report
  - Diagnostics (counts/samples) showing how many rows pass each condition

### Troubleshooting tips

- If SQL counts are high but the portal shows “No articles,” ensure the fetch slice is wide enough and that the app-side filters match the SQL above.
- Remember to quote WF_* columns in SQL.


