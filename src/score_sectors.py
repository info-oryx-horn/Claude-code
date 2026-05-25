"""Score brokerage-candidate sectors on two axes and a composite.

Reads one or more sector CSVs (schema in prompts/_sector_schema.md), computes
an AI-Impact score and a Problem-Severity score (each 0-100), blends them into
composite_priority, labels each sector's quadrant, and writes a ranked CSV.

Run from repo root:
    python src/score_sectors.py
    python src/score_sectors.py --input-glob 'data/sectors_seed_*.csv' --out data/sectors_ranked.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.sectors import (  # noqa: E402
    AI_IMPACT_WEIGHTS,
    APPLY_COMPETITION_PENALTY,
    APPLY_MARKET_SIZE_TILT,
    AXIS_MIDPOINT,
    COMPETITION_PENALTY_PER_POINT,
    COMPOSITE_ALPHA,
    COMPOSITE_MODE,
    MARKET_SIZE_MAX_BONUS,
    MARKET_SIZE_REF_USD,
    NEUTRAL_RATING,
    SEVERITY_WEIGHTS,
    TOP_REASONS_PER_AXIS,
)

IDENTITY_COLUMNS = [
    "sector_id",
    "sector_name",
    "parent_industry",
    "supply_side",
    "demand_side",
    "brokerage_form_today",
    "transaction_type",
]


def load_sectors(input_glob: str) -> pd.DataFrame:
    files = sorted(glob.glob(input_glob))
    if not files:
        raise SystemExit(f"No CSVs matched {input_glob}")
    frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in files]
    df = pd.concat(frames, ignore_index=True)
    if "sector_id" in df.columns:
        df = df.drop_duplicates(subset=["sector_id"], keep="first").reset_index(drop=True)
    return df


def rating(value) -> float:
    """Coerce a 1-5 cell to float; blank/invalid -> NEUTRAL_RATING, clamped 1-5."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float(NEUTRAL_RATING)
    s = str(value).strip()
    if s == "":
        return float(NEUTRAL_RATING)
    try:
        v = float(s)
    except ValueError:
        return float(NEUTRAL_RATING)
    return min(5.0, max(1.0, v))


def axis_score(row, weights: dict[str, float]) -> tuple[float, list[tuple[float, str]]]:
    """Weighted average of 1-5 factors, rescaled to 0-100.

    Returns the 0-100 score and per-factor (weighted_rating, factor) pairs so
    the caller can surface the top contributors.
    """
    total_w = sum(weights.values())
    weighted_sum = 0.0
    contributions: list[tuple[float, str]] = []
    for factor, w in weights.items():
        r = rating(row.get(factor))
        weighted_sum += w * r
        contributions.append((w * r, factor))
    avg = weighted_sum / total_w  # in [1, 5]
    score = 100.0 * (avg - 1.0) / 4.0  # rescale to [0, 100]
    return score, contributions


def to_int(value):
    if value is None or value == "" or pd.isna(value):
        return None
    s = str(value).replace(",", "").replace("$", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def composite(ai: float, severity: float) -> float:
    if COMPOSITE_MODE == "weighted_sum":
        return COMPOSITE_ALPHA * ai + (1.0 - COMPOSITE_ALPHA) * severity
    # default: geometric mean rewards being high on both axes
    return math.sqrt(max(0.0, ai) * max(0.0, severity))


def apply_modifiers(base: float, row) -> float:
    score = base
    if APPLY_MARKET_SIZE_TILT:
        tam = to_int(row.get("market_size_usd"))
        if tam and tam > 0:
            # log-scaled bonus: ref TAM -> 0 bonus, 10x ref -> full bonus span.
            decades = math.log10(tam / MARKET_SIZE_REF_USD)
            bonus = max(0.0, min(MARKET_SIZE_MAX_BONUS, MARKET_SIZE_MAX_BONUS * decades))
            score *= (1.0 + bonus)
    if APPLY_COMPETITION_PENALTY:
        comp = rating(row.get("incumbent_competition"))
        score -= COMPETITION_PENALTY_PER_POINT * max(0.0, comp - 3.0)
    return max(0.0, min(100.0, score))


def quadrant(ai: float, severity: float) -> str:
    hi_ai = ai >= AXIS_MIDPOINT
    hi_sev = severity >= AXIS_MIDPOINT
    if hi_ai and hi_sev:
        return "build_now"
    if hi_sev:
        return "painful_but_hard"
    if hi_ai:
        return "easy_but_minor"
    return "deprioritize"


def top_reasons(contributions: list[tuple[float, str]]) -> list[str]:
    ranked = sorted(contributions, key=lambda c: c[0], reverse=True)
    return [factor for _, factor in ranked[:TOP_REASONS_PER_AXIS]]


def score_row(row) -> dict:
    ai, ai_contrib = axis_score(row, AI_IMPACT_WEIGHTS)
    sev, sev_contrib = axis_score(row, SEVERITY_WEIGHTS)
    comp = apply_modifiers(composite(ai, sev), row)
    reasons = top_reasons(ai_contrib) + top_reasons(sev_contrib)
    return {
        "ai_impact_score": round(ai, 1),
        "problem_severity_score": round(sev, 1),
        "composite_priority": round(comp, 1),
        "quadrant": quadrant(ai, sev),
        "score_reasons": "|".join(reasons),
    }


SCORE_COLUMNS = [
    "composite_priority",
    "ai_impact_score",
    "problem_severity_score",
    "quadrant",
    "score_reasons",
]


def write_ranked(df: pd.DataFrame, out_path: Path) -> None:
    leading = SCORE_COLUMNS + [c for c in IDENTITY_COLUMNS if c in df.columns]
    rest = [c for c in df.columns if c not in leading]
    df = df.sort_values("composite_priority", ascending=False)[leading + rest]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glob", default="data/sectors_*.csv")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = load_sectors(args.input_glob)
    if df.empty:
        print("No sector rows to score.")
        return 0

    scores = df.apply(score_row, axis=1, result_type="expand")
    for col in SCORE_COLUMNS:
        df[col] = scores[col]

    out = (
        Path(args.out)
        if args.out
        else Path(f"data/sectors_ranked_{dt.date.today().isoformat()}.csv")
    )
    write_ranked(df, out)
    print(f"Scored {len(df)} sectors → {out}")

    print("\nQuadrant tally:")
    for q in ("build_now", "painful_but_hard", "easy_but_minor", "deprioritize"):
        print(f"  {q:<18} {(df['quadrant'] == q).sum()}")

    print("\nTop 10 by composite priority:")
    preview_cols = [
        "composite_priority",
        "ai_impact_score",
        "problem_severity_score",
        "quadrant",
        "sector_name",
    ]
    preview = df.sort_values("composite_priority", ascending=False).head(10)
    print(preview[[c for c in preview_cols if c in preview.columns]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
