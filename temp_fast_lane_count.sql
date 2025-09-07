-- Count articles that would qualify for fast lane
SELECT 
  'Fast Lane Count' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND (
    clients ILIKE '%Databricks%' OR
    clients ILIKE '%Starface%' OR
    clients ILIKE '%Bombas%' OR
    clients ILIKE '%WIP%' OR
    clients ILIKE '%KFC%'
  )

UNION ALL

-- Count total eligible articles for comparison
SELECT 
  'Total Eligible' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE

UNION ALL

-- Show breakdown by keyword
SELECT 
  'Databricks' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%Databricks%'

UNION ALL

SELECT 
  'Starface' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%Starface%'

UNION ALL

SELECT 
  'Bombas' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%Bombas%'

UNION ALL

SELECT 
  'WIP' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%WIP%'

UNION ALL

SELECT 
  'KFC' as category,
  COUNT(*) as count
FROM soup_dedupe
WHERE extraction_path = 2
  AND ("WF_Extraction_Complete" IS NULL OR "WF_Extraction_Complete" = FALSE)
  AND dedupe_status = 'original'
  AND "WF_Pre_Check_Complete" = TRUE
  AND clients ILIKE '%KFC%'

ORDER BY 
  CASE category
    WHEN 'Total Eligible' THEN 1
    WHEN 'Fast Lane Count' THEN 2
    ELSE 3
  END,
  category;

