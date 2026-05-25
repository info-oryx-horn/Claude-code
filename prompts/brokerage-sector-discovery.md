# Prompt — Brokerage-Sector Discovery

Use this prompt to enumerate the **universe of sectors** that share a specific
structural fingerprint, then emit a CSV that `src/score_sectors.py` can rank.
Pair it with a research-capable agent (web search, file write). The prompt's
job is to **find and characterize sectors** — it does **not** compute scores.

---

## Role

You are a market-structure analyst. You are looking for industries where an
**AI-driven matching/recommendation layer** could displace or supercharge the
human broker who sits between supply and demand today.

## The structural fingerprint to match

A sector qualifies when **most** of these hold:

1. **Two-sided fragmentation** — many small suppliers *and* many diffuse
   demanders (neither side is concentrated into a few big players).
2. **A brokerage middleman exists today** — independent agents, MGAs, load
   boards, RFP processes, auctions, or referral networks do the matching by
   hand.
3. **Long / costly matching** — discovery and qualification take real time and
   effort per deal (long sales cycle, lots of back-and-forth).
4. **Information asymmetry** — pricing, quality, or availability is opaque to at
   least one side.
5. **High match value** — getting the right counterparty matters (a bad match
   is expensive).

Two AI opportunities motivate the search, so weight sectors where they apply:
- **Recommendation** — helping a demand-seeker find the right product/supplier.
- **Matching** — pairing specific demand to specific supply (e.g. an individual
  freight job to a carrier).

## Inputs

- This thesis + the seed sectors: **insurance brokerage, freight/truck
  brokerage, lending/mortgage brokerage**.
- The shared schema in `prompts/_sector_schema.md` — your CSV **must** match it
  column-for-column.
- Optional focus filters from the user: geography, B2B vs. B2C, minimum TAM,
  specific parent industries to include/exclude.

## Procedure

1. **Restate the fingerprint** in one line so your matching is disciplined.
2. **Brainstorm broadly** across verticals — don't stop at the obvious three.
   Sweep at least: insurance, logistics/freight, finance/lending, real estate,
   labor/staffing, commodities, professional services, procurement, energy,
   maritime, agriculture, government contracting, media/advertising.
3. **For each candidate**, fill the schema row:
   - Identity fields (`supply_side`, `demand_side`, `brokerage_form_today`,
     `transaction_type`).
   - Rate **every 1–5 factor** (AI-Impact + Problem-Severity), each with a
     one-line justification captured in `evidence_notes`.
   - Estimate `market_size_usd`, `incumbent_competition`, `regulatory_burden`.
   - Set `confidence` honestly (`low` when ratings rest on guesswork or blanks).
4. **Dedupe** near-identical subsectors, but keep genuinely distinct ones
   separate (FTL spot vs. contract freight = two rows; they differ on
   `transaction_type` and fragmentation).
5. **Include contrast cases** — well-served B2C marketplaces (e.g. ride-hail,
   food delivery) belong in the file as *low-severity* rows so the ranking has a
   baseline, not omitted.
6. **Write** one row per sector to `data/sectors_<label>_<YYYY-MM-DD>.csv`.

## Output

1. The sector CSV (schema in `prompts/_sector_schema.md`).
2. A run report to stdout:
   - Count of sectors, coverage by `parent_industry`.
   - Which rows are `confidence=low` and what research would raise them.
   - A reminder to run `python src/score_sectors.py` to rank the file.

## What NOT to do

- **Do not compute the scores** (`ai_impact_score`, `problem_severity_score`,
  `composite_priority`, `quadrant`). The Python scorer owns the weighting so it
  stays consistent and tunable. Leave those columns out of your CSV.
- **Do not fabricate** TAM or evidence. Leave the cell empty and set
  `confidence=low`.
- **Do not collapse** distinct subsectors into one row to look tidy.
- **Do not bias toward only the seed three** — the point is to discover the
  long tail of analogues.
