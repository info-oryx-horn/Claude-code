# Sector Discovery Output Schema

The discovery prompt (`brokerage-sector-discovery.md`) emits **one CSV row per
candidate sector/subsector**. `src/score_sectors.py` reads that CSV and appends
the computed scores. The prompt fills the **identity**, **factor-rating**,
**context**, and **evidence** columns below. It must **never** fill the
score columns — those are computed downstream so the weighting stays in one
place (`config/sectors.py`).

All factor ratings are integers on a **1–5 scale**. Leave a cell **blank** if
you genuinely can't assess it (the scorer treats blank as the neutral midpoint
`3` and the row's `confidence` should reflect that). Never invent evidence.

## Columns (in this order)

### Identity / description
| # | Column | Type | Notes |
|---|---|---|---|
| 1 | `sector_id` | string | Stable slug, e.g. `freight-brokerage-ftl-spot`. Lowercase, hyphenated. |
| 2 | `sector_name` | string | Human-readable name. |
| 3 | `parent_industry` | string | Broad bucket: `insurance`, `logistics`, `finance`, `real_estate`, `labor`, `commodities`, `professional_services`, `procurement`, `energy`, `maritime`, `agriculture`, `govcon`, `media`, `other`. |
| 4 | `supply_side` | string | Who supplies (e.g. "owner-operator truckers"). |
| 5 | `demand_side` | string | Who demands (e.g. "shippers with one-off loads"). |
| 6 | `brokerage_form_today` | string | How matching happens now (independent agents, MGAs, load boards, RFPs, auctions, referral networks…). |
| 7 | `transaction_type` | enum | `one_off` \| `recurring` \| `contract` \| `mixed`. |

### AI-Impact factors (1–5; higher = AI can help more)
| # | Column | What a 5 means |
|---|---|---|
| 8 | `ai_matching_complexity` | Many attributes must align supply↔demand (route, timing, risk class, specs). |
| 9 | `ai_transaction_volume` | Very high deal/job frequency → abundant training signal and recurring ROI. |
| 10 | `ai_data_availability` | Supply & demand data is digitized and accessible. |
| 11 | `ai_personalization_need` | Each recommendation must be highly bespoke. |
| 12 | `ai_manual_brokering_reliance` | A human does almost all the matching today (large automation headroom). |
| 13 | `ai_document_language_intensity` | Work is dominated by documents/text (quotes, contracts, specs) where LLMs excel. |

### Problem-Severity factors (1–5; higher = bigger "migraine")
| # | Column | What a 5 means |
|---|---|---|
| 14 | `sev_supply_fragmentation` | Thousands of tiny, scattered suppliers. |
| 15 | `sev_demand_fragmentation` | Demand is diffuse and hard to aggregate. |
| 16 | `sev_search_friction` | Finding the right counterparty is slow and painful. |
| 17 | `sev_sales_cycle_length` | Cycles run months and burn effort per deal. |
| 18 | `sev_information_asymmetry` | Pricing/quality is opaque to one or both sides. |
| 19 | `sev_middleman_rent` | Incumbent intermediaries extract large margins (room to disrupt). |
| 20 | `sev_mismatch_cost` | A bad match is very costly (claims, downtime, defaults). |

### Context / composite modifiers (not part of the two axes)
| # | Column | Type | Notes |
|---|---|---|---|
| 21 | `market_size_usd` | integer | Rough TAM estimate, USD. Blank if unknown — do **not** write `0`. |
| 22 | `incumbent_competition` | 1–5 | Crowdedness of existing AI/tech players (5 = saturated). Used only if competition penalty is enabled in config. |
| 23 | `regulatory_burden` | 1–5 | Context only by default (5 = heavily regulated). |

### Evidence
| # | Column | Type | Notes |
|---|---|---|---|
| 24 | `evidence_notes` | string | Verbatim/cited support for the ratings. Empty if none — never fabricate. |
| 25 | `confidence` | enum | `high` \| `medium` \| `low`. Use `low` when ratings rest on estimates or blanks. |
| 26 | `date_scored` | ISO date | Date the row was assessed. |

## Score columns (appended by `src/score_sectors.py` — do NOT fill in the prompt)

`ai_impact_score` (0–100), `problem_severity_score` (0–100),
`composite_priority` (0–100), `quadrant`
(`build_now` \| `painful_but_hard` \| `easy_but_minor` \| `deprioritize`),
`score_reasons` (pipe-joined top contributing factors).

## Normalization rules

- **Ratings**: integers 1–5 only. Blank → scorer uses `3` (neutral) and you
  should reflect the uncertainty in `confidence`.
- **Currency**: integer USD. `$4.2B` → `4200000000`. Blank if unknown; never `0`.
- **One row per distinct subsector.** Do not collapse subsectors that differ on
  `transaction_type` or fragmentation (e.g. FTL spot vs. contract freight are
  separate rows).
- **Never invent evidence or TAM.** Leave the cell empty and set
  `confidence=low`.

## Output file naming

`data/sectors_<label>_<YYYY-MM-DD>.csv` (e.g. `data/sectors_seed_2026-05-25.csv`).
UTF-8, comma-delimited, RFC 4180 quoting.
