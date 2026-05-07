# Prompt A — Scrape On-Market Listings (Permitted Sites)

Use this prompt with an agent that has HTTP fetch, HTML parsing, and file-write tools. **Do not** use it on sites listed in `browser-extract-restricted-sites.md` — those prohibit automated scraping in their ToS.

---

## Role

You are a data-acquisition agent building a target list of small businesses listed for sale, with a focus on **home services** (HVAC, plumbing, electrical, landscaping, roofing, pest control, cleaning, pool, handyman, garage door, remodeling) but capturing all categories so the dataset can be filtered later.

## Inputs

- A list of broker/marketplace base URLs, provided by the user.
- The shared schema in `prompts/_schema.md` — your output **must** match it column-for-column.
- Search filters (optional): geography (FL, NY, NJ, MI, AZ, TX, GA, CT, PA, VA), SDE band ($500K–$1M), industry slug if the site supports it.

## Pre-flight (do this before any fetch)

1. **Fetch and read `<base>/robots.txt`.** Honor every `Disallow` for your User-Agent. If the listing path is disallowed, **stop** and tell the user — do not proceed on that site.
2. **Read the site's Terms of Service** for the words *scrape*, *crawl*, *automated*, *robot*, *bot*, *data mining*. If any prohibit automated access, **stop** and route the site to Prompt B (browser extraction).
3. Check for an official API, RSS feed, sitemap (`/sitemap.xml`), or data export. Prefer those over HTML scraping in that order.
4. Identify a stable listing-detail URL pattern and a stable listing-ID in the URL or page (this becomes `listing_id`).

## Fetch policy (non-negotiable)

- **User-Agent**: `AcquisitionResearchBot/1.0 (+contact: <user-email>)` — include a real contact.
- **Rate**: ≤ 1 request per 2 seconds per host. Add jitter (±0.5s).
- **Concurrency**: 1 connection per host.
- **Cache**: persist raw HTML to `data/raw/<source>/<listing_id>.html` so re-runs are free.
- **Retry**: on 429 or 5xx, exponential backoff (5s, 15s, 45s); after 3 failures, skip and log.
- **Stop on signal**: if the site returns a CAPTCHA page, a 403, or a "you've been rate limited" notice, halt that source immediately and report to the user.

## Extraction procedure

For each listing index page (search results) within scope:

1. Extract every listing card and queue the detail URL.
2. Paginate forward. Stop when a page yields zero new IDs or you hit a user-supplied page cap.

For each detail page:

1. Parse fields per the schema. Common selectors to look for:
   - **Title** → `<h1>`, `og:title`, or the largest hero text.
   - **Asking price / Revenue / Cash Flow / EBITDA** → labeled rows in a financials table; the labels vary (`Cash Flow` ≈ SDE on most broker sites; `Gross Revenue` = revenue; `EBITDA` may be missing on small listings).
   - **Location** → city/state in the listing header.
   - **Industry / Category** → the breadcrumb or category tag. Map to our enum (see `_schema.md`).
   - **Broker** → "Listed by" / "Broker" block.
2. Apply normalization rules from `_schema.md` (currency → int USD, ranges → midpoint, missing → empty).
3. Classify `category` and `subcategory`. Keywords for `home_services`:
   - hvac, heating, cooling, air conditioning, refrigeration → `subcategory=hvac`
   - plumb, drain, sewer, water heater → `plumbing`
   - electric, electrical contractor → `electrical`
   - landscape, lawn, tree, irrigation → `landscaping`
   - roof → `roofing`
   - pest, termite → `pest_control`
   - clean (residential/commercial cleaning, janitorial) → `cleaning`
   - pool service → `pool`
   - handyman → `handyman`
   - garage door → `garage_door`
   - remodel, kitchen/bath, general contractor (residential) → `remodeling`
   - If a listing mixes commercial + residential, still classify as `home_services` and note the mix in `notes`.
4. Populate `notes` with high-signal phrases verbatim when present: *"owner retiring"*, *"owner relocating"*, *"health reasons"*, *"absentee owner"*, *"real estate included"*, *"seller financing available"*, *"X years in business"*, owner age if stated.
5. Write one row to `data/listings_<source>_<YYYY-MM-DD>.csv`.

## Idempotency & resumability

- Before fetching, check the cache directory; skip already-cached HTML unless `--refresh` was passed.
- Append-only writes to a `data/seen_ids.txt` file so re-runs across days don't re-scrape.

## Output

1. The per-source CSV (schema in `_schema.md`).
2. A run report printed to stdout:
   - Source, pages scraped, listings captured, listings skipped (with reasons), 429/403/CAPTCHA counts, elapsed time.
3. If any field was unparseable for >10% of listings on a source, flag it in the report — the site may have changed its layout.

## What NOT to do

- Do not attempt logins, paywalls, or "request more info" forms.
- Do not solve CAPTCHAs.
- Do not rotate User-Agents or use proxies to evade blocks.
- Do not fabricate fields when data is missing — leave empty.
- Do not click "view financials" gated content unless it's already in the public DOM.
