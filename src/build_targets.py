"""Load all data/listings_*.csv files, dedupe, filter to acquisition
criteria in config/targets.py, score for owner-motivation signals, and
write a ranked target list to data/targets_<today>.csv.

Run from repo root:
    python src/build_targets.py
    python src/build_targets.py --input-glob 'data/listings_*.csv' --out data/targets.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.targets import (
    OWNER_AGE_HIGH,
    OWNER_AGE_LOW,
    OWNER_AGE_MID,
    PRICE_FLAG_BARGAIN_MULTIPLE,
    PRICE_FLAG_FAIR_MULTIPLE,
    PRICE_FLAG_MARKET_MULTIPLE,
    SDE_FROM_REVENUE_FALLBACK,
    SDE_MAX_USD,
    SDE_MIN_USD,
    SDE_SWEET_SPOT_MAX_USD,
    SDE_SWEET_SPOT_MIN_USD,
    TARGET_STATES,
    TARGET_TRADES,
)

OWNER_AGE_CACHE_PATH = ROOT / "data" / "owner_age_cache.csv"
ENRICH_COLUMNS = (
    "owner_name",
    "owner_age_estimate",
    "est_years_in_business",
    "owner_age_source",
)

RETIREMENT_RE = re.compile(
    r"\b(retir(?:e|ing|ement|ed)|owner\s*(?:age|aged)\s*(?:6\d|7\d|8\d)"
    r"|aging\s*owner|long[-\s]?time\s*owner)\b",
    re.I,
)
LIFE_EVENT_RE = re.compile(
    r"\b(reloc(?:ating|ation)|health\s*reasons?|family\s*reasons?"
    r"|personal\s*reasons?|estate\s*sale)\b",
    re.I,
)
REAL_ESTATE_RE = re.compile(
    r"\b(real\s*estate\s*included|building\s*included|owns?\s*the\s*building)\b",
    re.I,
)
ABSENTEE_RE = re.compile(r"\babsentee\s*owner\b", re.I)
YEARS_RE = re.compile(r"(\d{2,3})\s*\+?\s*years?\s*(?:in\s*business|established)", re.I)


def to_int(value) -> int | pd._libs.missing.NAType:
    if value is None or value == "" or pd.isna(value):
        return pd.NA
    s = str(value).replace(",", "").replace("$", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return pd.NA


def load_listings(input_glob: str) -> pd.DataFrame:
    files = sorted(glob.glob(input_glob))
    if not files:
        raise SystemExit(f"No CSVs matched {input_glob}")
    frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in files]
    return pd.concat(frames, ignore_index=True)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    for col in (
        "annual_revenue_usd",
        "annual_ebitda_usd",
        "annual_sde_usd",
        "asking_price_usd",
    ):
        df[col] = df[col].apply(to_int) if col in df.columns else pd.NA

    for col, transform in (
        ("location_state", lambda s: s.str.upper().str.strip()),
        ("subcategory", lambda s: s.str.lower().str.strip()),
        ("category", lambda s: s.str.lower().str.strip()),
        ("opportunity_title", lambda s: s.str.strip()),
    ):
        df[col] = transform(df[col]) if col in df.columns else ""

    df["notes"] = df["notes"].fillna("").astype(str) if "notes" in df.columns else ""

    def fill_id(row):
        existing = row.get("listing_id", "")
        if existing:
            return existing
        seed = (row.get("source", "") or "") + (
            row.get("listing_url", "") or row.get("opportunity_title", "") or ""
        )
        return "synth-" + hashlib.sha1(seed.encode()).hexdigest()[:12]

    df["listing_id"] = df.apply(fill_id, axis=1)
    return df


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Exact-ID dedup, then fuzzy dedup on title within (state, similar SDE)."""
    df = df.drop_duplicates(subset=["listing_id"], keep="first").reset_index(drop=True)

    keep_mask = [True] * len(df)
    titles_norm = df["opportunity_title"].fillna("").map(
        lambda t: re.sub(r"[^a-z0-9 ]", " ", t.lower())
    )

    for i in range(len(df)):
        if not keep_mask[i]:
            continue
        for j in range(i + 1, len(df)):
            if not keep_mask[j]:
                continue
            if df.at[i, "location_state"] != df.at[j, "location_state"]:
                continue
            sde_i, sde_j = df.at[i, "annual_sde_usd"], df.at[j, "annual_sde_usd"]
            if pd.notna(sde_i) and pd.notna(sde_j):
                if abs(sde_i - sde_j) > 0.10 * max(sde_i, sde_j):
                    continue
            if fuzz.token_set_ratio(titles_norm.iat[i], titles_norm.iat[j]) >= 90:
                # Drop the row with fewer populated fields.
                fill_i = df.iloc[i].replace("", pd.NA).notna().sum()
                fill_j = df.iloc[j].replace("", pd.NA).notna().sum()
                drop = j if fill_i >= fill_j else i
                keep_mask[drop] = False
                if drop == i:
                    break  # stop comparing from i; it's gone
    return df[keep_mask].reset_index(drop=True)


def enrich_owner_age(df: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """Merge owner-age data from data/owner_age_cache.csv.

    Cache schema: listing_id, business_name, owner_name, owner_age_estimate,
    est_years_in_business, source, notes. Match by listing_id first, then by
    case-insensitive business_name (skipping "Confidential").
    """
    if not cache_path.exists():
        for col in ENRICH_COLUMNS:
            df[col] = ""
        return df

    cache = pd.read_csv(cache_path, dtype=str, keep_default_na=False)
    if "source" in cache.columns:
        cache = cache.rename(columns={"source": "owner_age_source"})
    for col in ENRICH_COLUMNS:
        if col not in cache.columns:
            cache[col] = ""

    by_id: dict[str, dict[str, str]] = {}
    by_name: dict[str, dict[str, str]] = {}
    for _, row in cache.iterrows():
        entry = {col: str(row.get(col, "") or "") for col in ENRICH_COLUMNS}
        lid = str(row.get("listing_id", "") or "").strip()
        if lid:
            by_id[lid] = entry
        bn = str(row.get("business_name", "") or "").lower().strip()
        if bn and bn != "confidential" and bn not in by_name:
            by_name[bn] = entry

    def lookup(row):
        lid = str(row.get("listing_id", "") or "")
        if lid in by_id:
            return by_id[lid]
        bn = str(row.get("business_name", "") or "").lower().strip()
        if bn in by_name:
            return by_name[bn]
        return {col: "" for col in ENRICH_COLUMNS}

    enriched = df.apply(lookup, axis=1, result_type="expand")
    for col in ENRICH_COLUMNS:
        df[col] = enriched[col]
    return df


def compute_price_flags(df: pd.DataFrame) -> pd.DataFrame:
    sde = pd.to_numeric(df["annual_sde_usd"], errors="coerce")
    price = pd.to_numeric(df["asking_price_usd"], errors="coerce")
    multiple = (price / sde).where(sde.notna() & price.notna() & (sde > 0))
    df["sde_multiple"] = multiple.round(2)

    def classify(m):
        if pd.isna(m):
            return "unknown"
        if m < PRICE_FLAG_BARGAIN_MULTIPLE:
            return "bargain"
        if m < PRICE_FLAG_FAIR_MULTIPLE:
            return "fair"
        if m < PRICE_FLAG_MARKET_MULTIPLE:
            return "market"
        return "overpriced"

    df["price_flag"] = df["sde_multiple"].apply(classify)
    return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    in_trades = df["subcategory"].isin(TARGET_TRADES)
    in_states = df["location_state"].isin(TARGET_STATES)

    sde = df["annual_sde_usd"]
    rev = df["annual_revenue_usd"]
    sde_proxy = sde.where(
        sde.notna(),
        rev.where(rev.notna(), other=pd.NA).astype("Float64") * SDE_FROM_REVENUE_FALLBACK,
    )
    in_band = sde_proxy.between(SDE_MIN_USD, SDE_MAX_USD)

    return df[in_trades & in_states & in_band].copy()


def score_row(row) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    notes = row.get("notes") or ""

    # Owner age — prefer cached hard data; fall back to retirement regex.
    age_str = str(row.get("owner_age_estimate") or "").strip()
    age_score = 0
    if age_str:
        try:
            age = int(age_str)
        except ValueError:
            age = None
        if age is not None:
            if age >= OWNER_AGE_HIGH:
                age_score = 30
            elif age >= OWNER_AGE_MID:
                age_score = 20
            elif age >= OWNER_AGE_LOW:
                age_score = 10
            if age_score:
                score += age_score
                reasons.append(f"owner_age_{age}")
    if age_score == 0 and RETIREMENT_RE.search(notes):
        score += 30
        reasons.append("retirement_signal")

    if LIFE_EVENT_RE.search(notes):
        score += 15
        reasons.append("life_event")
    if REAL_ESTATE_RE.search(notes):
        score += 10
        reasons.append("re_included")
    if ABSENTEE_RE.search(notes):
        score -= 5
        reasons.append("absentee_-5")

    # Years in business — prefer cached value, fall back to notes regex.
    years_str = str(row.get("est_years_in_business") or "").strip()
    years: int | None = None
    if years_str:
        try:
            years = int(years_str)
        except ValueError:
            years = None
    if years is None:
        m = YEARS_RE.search(notes)
        if m:
            years = int(m.group(1))
    if years is not None:
        if years >= 30:
            score += 20
            reasons.append(f"{years}yrs")
        elif years >= 20:
            score += 10
            reasons.append(f"{years}yrs")

    sde = row.get("annual_sde_usd")
    if pd.notna(sde) and SDE_SWEET_SPOT_MIN_USD <= sde <= SDE_SWEET_SPOT_MAX_USD:
        score += 15
        reasons.append("sde_sweet_spot")

    sub = row.get("subcategory") or ""
    if sub in ("hvac", "plumbing", "electrical"):
        score += 10
        reasons.append(f"trade_{sub}")
    elif sub == "landscaping":
        score += 5
        reasons.append("trade_landscaping")

    flag = row.get("price_flag") or ""
    if flag == "bargain":
        score += 10
        reasons.append("bargain_price")
    elif flag == "overpriced":
        score -= 5
        reasons.append("overpriced_-5")

    return score, "|".join(reasons)


OUTPUT_COLUMNS = [
    "motivation_score",
    "score_reasons",
    "listing_id",
    "source",
    "opportunity_title",
    "business_name",
    "category",
    "subcategory",
    "location_city",
    "location_state",
    "annual_revenue_usd",
    "annual_ebitda_usd",
    "annual_sde_usd",
    "asking_price_usd",
    "sde_multiple",
    "price_flag",
    "owner_name",
    "owner_age_estimate",
    "est_years_in_business",
    "owner_age_source",
    "financials_period",
    "broker_name",
    "listing_url",
    "listing_date_seen",
    "notes",
]


def write_targets(df: pd.DataFrame, out_path: Path) -> None:
    cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
    df = df.sort_values(
        ["motivation_score", "annual_sde_usd"], ascending=[False, False]
    )[cols]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glob", default="data/listings_*.csv")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = load_listings(args.input_glob)
    n_loaded = len(df)
    df = normalize(df)
    df = dedupe(df)
    n_deduped = len(df)
    df = apply_filters(df)
    n_filtered = len(df)

    print(
        f"Loaded {n_loaded} listings → {n_deduped} after dedup → "
        f"{n_filtered} match criteria"
    )
    if df.empty:
        return 0

    df = enrich_owner_age(df, OWNER_AGE_CACHE_PATH)
    df = compute_price_flags(df)

    scores = df.apply(score_row, axis=1, result_type="expand")
    df["motivation_score"] = scores[0].astype(int)
    df["score_reasons"] = scores[1]

    out = (
        Path(args.out)
        if args.out
        else Path(f"data/targets_{dt.date.today().isoformat()}.csv")
    )
    write_targets(df, out)
    print(f"Wrote {n_filtered} ranked targets to {out}")
    print()
    print("Top 10 by motivation score:")
    preview = df.sort_values("motivation_score", ascending=False).head(10)
    print(
        preview[
            [
                "motivation_score",
                "subcategory",
                "location_state",
                "annual_sde_usd",
                "sde_multiple",
                "price_flag",
                "owner_age_estimate",
                "opportunity_title",
            ]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
