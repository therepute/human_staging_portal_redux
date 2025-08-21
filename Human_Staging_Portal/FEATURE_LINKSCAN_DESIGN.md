# LinkScan: Stealth Background Target-Link Detection (Design)

## Goal
Quietly detect whether an article page contains links to target domains (e.g., `bombas.com`) while the human continues scraping normally in the portal. This runs fully in the background, is ultra-low-rate (~1% of opens), and is extremely stealthy.

## Non-Goals
- Do not alter the user’s “Open Story” flow or block the UI.
- Do not deep crawl; only inspect the single article page.
- Do not implement full anti-bot evasion beyond prudent hardening.

## High-Level Flow
1. User clicks “Open Story” (article window opens as usual).
2. UI quietly POSTs the Story URL and target domains to a background endpoint.
3. Backend performs a fast HTML fetch + BeautifulSoup parse.
4. If needed, backend falls back to a headless render (Playwright) to get dynamic content, re-parse, and extract links.
5. Backend stores results (and optionally attaches to the article record), then exposes a small status/result API.
6. UI can poll once or twice to display a tiny badge: e.g., “Targets found: bombas.com (2 links)”.

## Components
- Config:
  - `Human_Staging_Portal/config/target_link_domains.yaml` (allowlist of domains to detect; e.g., `["bombas.com", "acme.com"]`).
  - Feature flag (`LINKSCAN_ENABLED=true/false`) and sampling rate (`LINKSCAN_SAMPLE_PCT=1`).
  - Per-site login recipes (optional): `Human_Staging_Portal/config/login_recipes.yaml`.
- API:
  - `POST /api/linkscan/start` → enqueue/trigger background scan. Body: `{ url, soup_dedupe_id?, outlet_name?, targets? }`.
  - `GET /api/linkscan/status?id=...` (or `?url=...`) → returns `{ status, found, matches, method, duration_ms, error? }`.
- Workers:
  - In-process background task runner (FastAPI background task) or a simple async task queue.
- Fetchers:
  - Fast path: `requests` (or `httpx`) + BeautifulSoup.
  - Fallback: Playwright headless Chromium with persistent auth storage per outlet.
- Storage:
  - Caching: per-URL cache (e.g., 1 hour TTL) to avoid repeat fetching.
  - Results persistence: either new table or columns on existing table (see Data Model).

## Stealth & Safety
- Rate & sampling:
  - Only run on “Open Story”.
  - Sample ~1% of events (configurable) with random jitter.
  - Never run twice consecutively on the same outlet; rotate fairly.
- Minimal footprint:
  - Single page only, 2–4s timeout for fast path, 5–7s cap for render path.
  - Block heavy resources in Playwright (images, media, fonts, analytics) via request interception.
  - No deep crawling; parse only the article DOM.
- Identity & sessions:
  - Use realistic User-Agent, Accept-Language, timezone consistent with host.
  - Reuse logged-in sessions per outlet (stored via Playwright storage state), where allowed.
- Anti-bot hardening:
  - Headless fingerprint reductions (viewport, fonts, navigator props, WebGL contexts where possible).
  - Exponential backoff on 403/429; automatic backoff for that outlet for a period.
  - Respect robots.txt/ToS where applicable; allow per-outlet opt-out.
- Security:
  - Strict SSRF guard: only `http`/`https`, DNS resolve and block private IP ranges, limit redirects (max 3), limit response size (e.g., 4–8 MB), strict timeouts.

## Data Model Options
Choose one depending on how you want to surface and audit results.

- Option A: Columns on `the_soups` (minimal integration)
  - `Targets_Present` (boolean)
  - `Targets_Domains` (jsonb) — e.g., `["bombas.com"]`
  - `Targets_Sample_Links` (jsonb) — small list of sample URLs
  - `LinkScan_Status` (text enum: success|timeout|blocked|error)
  - `LinkScan_Method` (text enum: requests|playwright)
  - `LinkScan_Duration_ms` (int)
  - `LinkScan_Scanned_At` (timestamp)
  - Pros: Simple, visible next to other article fields. Cons: Adds columns even for non-scanned rows.

- Option B: New table `linkscan_results`
  - Columns: `id` (uuid), `soup_dedupe_id` (text, nullable), `url` (text), `url_hash` (text), `outlet_domain` (text), `targets_present` (bool), `domains` (jsonb), `sample_links` (jsonb), `method` (text), `status` (text), `duration_ms` (int), `scanned_at` (timestamp), `error` (text)
  - Pros: Clean separation, multiple scans possible, easy to extend. Cons: Requires join to view from article.

- Option C: Hybrid
  - Minimal boolean `Targets_Present` on `the_soups`, with full payload in `linkscan_results` keyed by `soup_dedupe_id`/`url_hash`.

Migration plan suggestion: Start with Option B (new table), then optionally add a single boolean to `the_soups` if you want an at-a-glance column.

## API Contracts (proposed)
- `POST /api/linkscan/start`
  - Request:
    ```json
    {
      "url": "https://example.com/article",
      "soup_dedupe_id": "GA_20250731_185915_000002",
      "outlet_name": "Wall Street Journal",
      "targets": ["bombas.com"]
    }
    ```
  - Response:
    ```json
    { "success": true, "id": "b5db...", "status": "queued" }
    ```

- `GET /api/linkscan/status?id=...`
  - Response:
    ```json
    {
      "success": true,
      "status": "done",
      "found": true,
      "matches": [
        { "domain": "bombas.com", "urls": ["https://.../utm=...", "https://..."] }
      ],
      "method": "playwright",
      "duration_ms": 2210,
      "scanned_at": "2025-08-15T19:22:10Z"
    }
    ```

## Parsing Algorithm
- Normalize URL (follow 1–2 redirects). Validate scheme and public IP only.
- Fetch Path A (requests → BeautifulSoup):
  - Parse `<a href>`, `<link href>`, `<script src>`, `<img src>`, `<iframe src>`, canonical `<link rel=canonical>`, and meta `og:url`.
  - Extract absolute URLs. Deduplicate.
- If content empty or minimal → Fetch Path B (Playwright):
  - Use persistent context per outlet (stored cookies). Intercept and block images/media/ads.
  - Wait for `networkidle` or a short settle (e.g., 2s), then `page.content()` and parse same as above.
- Domain matching:
  - Normalize to eTLD+1 (effective top-level + 1) and compare `endswith` against each target domain (so `shop.bombas.com` matches `bombas.com`).
  - Cap results; store a small sample of matching URLs.

## Credential-Aware Login (Optional)
- `config/login_recipes.yaml` per outlet:
  - Steps: navigate to signin, fill email, fill password, click submit, wait for selector.
- On first run (per outlet), auto-login (if safe and allowed), then persist storage state to disk.
- Subsequent runs reuse storage state silently; if session expires, auto-login again.
- If MFA/SSO appears, mark `status=need_manual_login` and skip until someone performs a one-time maintenance login using a non-headless run (out-of-band).

## UI Integration
- On “Open Story”:
  - Continue opening the article window.
  - In parallel, call `POST /api/linkscan/start`.
  - Optionally poll `GET /api/linkscan/status` once or twice over ~10s for a quick badge.
- Badge:
  - “Targets found: bombas.com (2)” → tiny label near `Story Link` field.
  - “No targets detected” or “Scan failed (timeout)” silently logged; minimal/no noise.

## Configuration
- `LINKSCAN_ENABLED` (default false).
- `LINKSCAN_SAMPLE_PCT` (default 1.0).
- `LINKSCAN_MAX_CONCURRENCY` (default 1–2 for headless).
- `LINKSCAN_TIMEOUT_FAST_MS` (default 3000), `LINKSCAN_TIMEOUT_RENDER_MS` (default 7000).
- `LINKSCAN_DENYLIST_DOMAINS` (e.g., sensitive sites).
- `LINKSCAN_ALLOWLIST_DOMAINS` (optional; if set, scan only these outlets).

## Observability
- Logs: per scan → method, status, duration, outlet, and matched domains count.
- Metrics: success rate, 403/429 rate per outlet, avg duration.
- Alerts: sustained 403/429 → auto backoff and optional alert.

## Local Development & Testing
- Run with `LINKSCAN_ENABLED=true` but `LINKSCAN_SAMPLE_PCT=100` in dev.
- Test with known public pages that contain target links.
- Manual switch to non-headless Playwright for writing/validating login recipes.

## Rollout Plan
1. Ship disabled behind `LINKSCAN_ENABLED=false`.
2. Enable in staging with `1%` sampling, allowlist a few outlets, and a single target domain.
3. Observe logs/metrics for a week; adjust timeouts and recipes.
4. Enable in production at `1%` with kill switch ready.

## Open Questions
- Exact table(s) to persist results: preference for Option B (new `linkscan_results`) vs. Option A minimal columns on `the_soups`.
- Target domains source of truth: YAML vs. Supabase table.
- Whether to surface a tiny indicator in the Recent panel.

---
This document describes the approach only. No implementation is included yet. When ready, we’ll add a new `features/linkscan/` module (router, worker, scanners, config loaders) and UI hooks guarded by a feature flag.

