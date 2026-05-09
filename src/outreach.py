"""Outreach tracker — maintains data/outreach.csv as a CRM-lite view of
target listings, keyed by listing_id.

Commands:
    python src/outreach.py sync     # add new high-score targets at status=queued
    python src/outreach.py status   # print status report

The targets CSV is read-only output of build_targets.py; outreach.csv is
the user-maintained state. They join on listing_id.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.targets import OUTREACH_SYNC_THRESHOLD

OUTREACH_PATH = ROOT / "data" / "outreach.csv"

OUTREACH_COLUMNS = [
    "listing_id",
    "status",
    "first_contact_date",
    "last_contact_date",
    "contact_method",
    "contact_name",
    "next_action",
    "next_action_date",
    "notes",
    "added_date",
]

VALID_STATUSES = (
    "queued",
    "researching",
    "contacted",
    "replied",
    "ndaed",
    "diligence",
    "loi",
    "passed",
    "dead",
    "won",
)
ACTIVE_STATUSES = ("queued", "researching", "contacted", "replied", "ndaed", "diligence", "loi")


def latest_targets() -> pd.DataFrame:
    paths = sorted(glob.glob(str(ROOT / "data" / "targets_*.csv")))
    if not paths:
        raise SystemExit("No data/targets_*.csv yet. Run `python src/build_targets.py` first.")
    return pd.read_csv(paths[-1], dtype=str, keep_default_na=False)


def load_outreach() -> pd.DataFrame:
    if OUTREACH_PATH.exists():
        return pd.read_csv(OUTREACH_PATH, dtype=str, keep_default_na=False)
    return pd.DataFrame(columns=OUTREACH_COLUMNS)


def save_outreach(df: pd.DataFrame) -> None:
    OUTREACH_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[OUTREACH_COLUMNS].to_csv(OUTREACH_PATH, index=False)


def cmd_sync(args: argparse.Namespace) -> int:
    targets = latest_targets()
    targets["motivation_score"] = pd.to_numeric(
        targets["motivation_score"], errors="coerce"
    ).fillna(0).astype(int)

    outreach = load_outreach()
    existing_ids = set(outreach["listing_id"]) if not outreach.empty else set()

    new = targets[
        (targets["motivation_score"] >= args.threshold)
        & (~targets["listing_id"].isin(existing_ids))
    ]
    if new.empty:
        print(f"No new targets at score ≥ {args.threshold}.")
        return 0

    today = dt.date.today().isoformat()
    rows = pd.DataFrame(
        {
            "listing_id": new["listing_id"].values,
            "status": "queued",
            "first_contact_date": "",
            "last_contact_date": "",
            "contact_method": "",
            "contact_name": "",
            "next_action": "research_owner",
            "next_action_date": today,
            "notes": "",
            "added_date": today,
        }
    )
    save_outreach(pd.concat([outreach, rows], ignore_index=True))
    print(f"Added {len(new)} target(s) at status=queued → {OUTREACH_PATH.relative_to(ROOT)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    targets = latest_targets()
    outreach = load_outreach()
    if outreach.empty:
        print("Outreach tracker is empty. Run `python src/outreach.py sync` first.")
        return 0

    join_cols = [
        "listing_id",
        "opportunity_title",
        "subcategory",
        "location_state",
        "annual_sde_usd",
        "asking_price_usd",
        "sde_multiple",
        "price_flag",
        "owner_age_estimate",
        "motivation_score",
    ]
    available = [c for c in join_cols if c in targets.columns]
    merged = outreach.merge(targets[available], on="listing_id", how="left")
    merged["motivation_score"] = pd.to_numeric(
        merged.get("motivation_score", 0), errors="coerce"
    ).fillna(0).astype(int)

    today = dt.date.today().isoformat()
    print("=" * 60)
    print(f"Outreach status — {today}   ({len(merged)} listing(s))")
    print("=" * 60)

    counts = merged["status"].value_counts()
    print("\nBy status:")
    for status, count in counts.items():
        print(f"  {status:<12} {count}")

    overdue = merged[
        (merged["next_action_date"].astype(str) != "")
        & (merged["next_action_date"].astype(str) < today)
        & (merged["status"].isin(ACTIVE_STATUSES))
    ]
    if not overdue.empty:
        print(f"\nOverdue follow-ups: {len(overdue)}")
        cols = ["listing_id", "status", "next_action", "next_action_date", "opportunity_title"]
        print(overdue[[c for c in cols if c in overdue.columns]].to_string(index=False))

    queued = merged[merged["status"] == "queued"].sort_values(
        "motivation_score", ascending=False
    )
    if not queued.empty:
        print(f"\nTop queued by motivation score:")
        cols = [
            "motivation_score",
            "subcategory",
            "location_state",
            "annual_sde_usd",
            "price_flag",
            "owner_age_estimate",
            "opportunity_title",
        ]
        print(queued[[c for c in cols if c in queued.columns]].head(10).to_string(index=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sync = sub.add_parser("sync", help="Add new high-score targets to the tracker")
    sync.add_argument("--threshold", type=int, default=OUTREACH_SYNC_THRESHOLD)
    sync.set_defaults(func=cmd_sync)

    status = sub.add_parser("status", help="Print status report")
    status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
