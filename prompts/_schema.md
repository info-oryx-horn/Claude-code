# Shared Output Schema

Both prompts (`scrape-permitted-sites.md` and `browser-extract-restricted-sites.md`) produce CSVs with **identical columns** so that outputs from any source can be concatenated and deduped downstream.

## Columns (in this order)

| # | Column | Type | Required | Notes |
|---|---|---|---|---|
| 1 | `listing_id` | string | yes | Stable unique key. Format: `<source-slug>-<site-listing-id>`. If the site exposes no ID, use a SHA1 of `source + listing_url`. |
| 2 | `source` | string | yes | Lowercase site slug, e.g. `bizbuysell`, `transworld`, `benchmark`, `bizquest`, `sunbelt`, `murphy`, `businessbroker`. |
| 3 | `listing_url` | string | yes | Canonical URL to the listing detail page. |
| 4 | `opportunity_title` | string | yes | The headline/title exactly as displayed. |
| 5 | `business_name` | string | yes | Legal / operating name. Use `"Confidential"` if the listing is anonymized. |
| 6 | `annual_revenue_usd` | integer | yes | Strip `$` and `,`. Empty if not disclosed (do **not** write `0`). |
| 7 | `annual_ebitda_usd` | integer | yes | Same rules as revenue. |
| 8 | `annual_sde_usd` | integer | yes | "Cash flow" on broker sites usually = SDE; capture there. |
| 9 | `category` | enum | yes | One of: `home_services`, `manufacturing`, `retail`, `food_service`, `automotive`, `distribution`, `professional_services`, `construction`, `healthcare`, `technology`, `other`. |
| 10 | `subcategory` | string | yes | For `home_services`: `hvac`, `plumbing`, `electrical`, `landscaping`, `roofing`, `pest_control`, `cleaning`, `pool`, `handyman`, `garage_door`, `remodeling`, `other`. Empty for non-home-services. |
| 11 | `location_city` | string | recommended | |
| 12 | `location_state` | string | recommended | 2-letter USPS code. |
| 13 | `asking_price_usd` | integer | recommended | Used downstream for SDE multiple sanity checks. |
| 14 | `financials_period` | enum | recommended | `ttm`, `annual_2024`, `annual_2023`, `projected`, `unknown`. Prefer trailing-12-months actuals when multiple are shown. |
| 15 | `broker_name` | string | recommended | Listing broker / firm. |
| 16 | `listing_date_seen` | ISO date | yes | Date the listing was captured (today's date). |
| 17 | `notes` | string | optional | Free text. Flag if real estate is included, owner financing offered, owner retiring, owner age mentioned, etc. — these are high-signal for our motivation score. |

## Normalization rules

- **Currency**: integer USD only. `$1.2M` → `1200000`. `$850K` → `850000`. Ranges (`$500K–$750K`) → take the midpoint and append `range_midpoint` to `notes`.
- **Categorization**: classify from the listing's stated industry/category, not the title. If the listing is in a broker's "Services" or "Building & Construction" bucket but is clearly a home service trade (HVAC, plumbing, etc.), set `category=home_services` and fill `subcategory` accordingly.
- **Anonymized listings**: `business_name="Confidential"` is normal and expected — do not skip these.
- **Missing fields**: leave the cell empty. Never invent, estimate, or carry over from another listing.
- **One row per listing**. If the same business appears on multiple sites, capture both — dedup happens downstream by fuzzy matching on title + location + revenue.

## Output file naming

`data/listings_<source-slug>_<YYYY-MM-DD>.csv`

UTF-8, comma-delimited, RFC 4180 quoting (quote any field containing `,`, `"`, or newlines; escape `"` as `""`).
