"""User-editable acquisition criteria.

Edit values here to change what `src/build_targets.py` filters and scores.
"""

# 2-letter USPS codes for target geography.
TARGET_STATES = ["FL", "NY", "NJ", "MI", "AZ", "TX", "GA", "CT", "PA", "VA"]

# Metro reference (informational only — filter is at state level).
TARGET_METROS = {
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville"],
    "NY": ["New York", "Long Island", "Buffalo"],
    "NJ": ["Newark", "Jersey City"],
    "MI": ["Detroit"],
    "AZ": ["Phoenix"],
    "TX": ["Dallas", "Fort Worth", "Austin", "Houston"],
    "GA": ["Atlanta"],
    "CT": [],
    "PA": ["Philadelphia", "Pittsburgh"],
    "VA": [],
}

# Subcategory slugs used in CSVs (see prompts/_schema.md for the full enum).
# "mechanical" on broker sites usually maps to hvac in our taxonomy.
TARGET_TRADES = ["hvac", "plumbing", "electrical", "landscaping"]

# SDE band, USD.
SDE_MIN_USD = 500_000
SDE_MAX_USD = 1_000_000

# Sweet spot inside the band (used by scorer only).
SDE_SWEET_SPOT_MIN_USD = 700_000
SDE_SWEET_SPOT_MAX_USD = 900_000

# When SDE is missing, fall back to revenue * this fraction for the SDE-band
# filter only (not for the score). Home-service businesses typically run
# 15–25% SDE margin; 0.20 is a defensible midpoint.
SDE_FROM_REVENUE_FALLBACK = 0.20

# Asking-price / SDE multiple thresholds for the price_flag column.
# Below BARGAIN -> "bargain"; below FAIR -> "fair"; below MARKET -> "market";
# above MARKET -> "overpriced".
PRICE_FLAG_BARGAIN_MULTIPLE = 2.5
PRICE_FLAG_FAIR_MULTIPLE = 3.5
PRICE_FLAG_MARKET_MULTIPLE = 4.5

# Owner-age scoring thresholds (used when owner_age_estimate is known).
OWNER_AGE_HIGH = 65   # +30 (max retirement signal)
OWNER_AGE_MID = 60    # +20
OWNER_AGE_LOW = 55    # +10

# Minimum motivation score that auto-adds a target to data/outreach.csv on sync.
OUTREACH_SYNC_THRESHOLD = 30
