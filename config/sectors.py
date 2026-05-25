"""User-editable scoring parameters for brokerage-sector discovery.

Edit values here to change how `src/score_sectors.py` weights factors and
blends the two axes into a composite priority. All factor ratings come in on a
1-5 scale (see prompts/_sector_schema.md); the scorer rescales each axis to
0-100.
"""

# --- AI-Impact axis -------------------------------------------------------
# Higher weight = factor matters more for "can AI move the needle here".
# Defaults emphasize matching complexity, automation headroom, and whether the
# data even exists to train on.
AI_IMPACT_WEIGHTS = {
    "ai_matching_complexity": 1.5,
    "ai_transaction_volume": 1.0,
    "ai_data_availability": 1.5,
    "ai_personalization_need": 1.0,
    "ai_manual_brokering_reliance": 1.5,
    "ai_document_language_intensity": 1.0,
}

# --- Problem-Severity axis ("migraine level") -----------------------------
# Defaults emphasize the friction of finding a counterparty and how fragmented
# / rent-heavy the status quo is.
SEVERITY_WEIGHTS = {
    "sev_supply_fragmentation": 1.25,
    "sev_demand_fragmentation": 1.25,
    "sev_search_friction": 1.5,
    "sev_sales_cycle_length": 1.0,
    "sev_information_asymmetry": 1.0,
    "sev_middleman_rent": 1.25,
    "sev_mismatch_cost": 1.0,
}

# Rating used when a factor cell is blank (neutral midpoint of the 1-5 scale).
NEUTRAL_RATING = 3

# How many top factor contributors to list in score_reasons per row.
TOP_REASONS_PER_AXIS = 3

# --- Composite ------------------------------------------------------------
# "geometric"     -> sqrt(ai * severity): a sector must score high on BOTH axes
#                    to rank well (a painful-but-AI-resistant sector won't top
#                    the list, nor will an easy AI win on a trivial problem).
# "weighted_sum"  -> COMPOSITE_ALPHA * ai + (1 - COMPOSITE_ALPHA) * severity.
COMPOSITE_MODE = "geometric"
COMPOSITE_ALPHA = 0.5  # only used when COMPOSITE_MODE == "weighted_sum"

# --- Optional composite modifiers (off by default) ------------------------
# A crude "winnability" lean on top of the raw axes. Both leave the two axis
# scores untouched; they only nudge composite_priority.
APPLY_MARKET_SIZE_TILT = False
# Multiplier span: a sector at MARKET_SIZE_REF_USD gets ~1.0x; bigger markets
# get up to (1 + MARKET_SIZE_MAX_BONUS)x, scaled by log10 of TAM.
MARKET_SIZE_REF_USD = 1_000_000_000
MARKET_SIZE_MAX_BONUS = 0.20

APPLY_COMPETITION_PENALTY = False
# Each point of incumbent_competition above 3 subtracts this many composite
# points (so a saturated 5/5 sector loses 2 * COMPETITION_PENALTY_PER_POINT).
COMPETITION_PENALTY_PER_POINT = 4.0

# --- Quadrant cutoffs -----------------------------------------------------
# Split the 2x2 on each axis at this 0-100 cutoff.
#   high AI / high severity -> build_now
#   low  AI / high severity -> painful_but_hard
#   high AI / low  severity -> easy_but_minor
#   low  AI / low  severity -> deprioritize
# NOTE: this is the "high" threshold, not the arithmetic middle of the scale.
# A discovery CSV is pre-filtered to plausible candidates, so most factors land
# 3-5 and the rescaled axis scores cluster ~60-90. 70 (≈ a 4/5 average) puts
# roughly the top half of credible candidates into the "high" band so the 2x2
# discriminates. Lower it toward 50 for an absolute "above-neutral" reading.
AXIS_MIDPOINT = 70.0
