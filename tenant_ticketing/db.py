import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Overridable so a deployment can point this at a persistent disk (e.g. Render's
# mounted volume) instead of the container's ephemeral local filesystem.
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "ticketing.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('tenant', 'handyman', 'landlord')),
    lease_id TEXT,
    property TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_email TEXT NOT NULL,
    lease_id TEXT,
    property TEXT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_queue' CHECK (status IN ('in_queue', 'in_process', 'complete')),
    priority INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    photo_1 TEXT,
    photo_2 TEXT,
    FOREIGN KEY (tenant_email) REFERENCES users (email)
);
"""

# Seeded from the tenant roster provided (lease roll) plus the handyman and landlord.
SEED_USERS = [
    ("garyrunion67@gmail.com", "Gary Runion", "tenant", "22727 Rein Studio 2026", "22727 Rein"),
    ("jaecourture@gmail.com", "Jasmine Williams", "tenant", "22174 Cushing Upper 2026-2027", "22174 Cushing"),
    ("cchobod@gmail.com", "Caitlyn Chobod", "tenant", "22727 Rein 2 Bed Smaller 2026", "22727 Rein"),
    ("djuan.drake@gmail.com", "Djuan", "tenant", "22727 Rein 1 Bed 2026 copy", "22727 Rein"),
    ("lislis8585b@gmail.com", "Lisa C & Lisa B", "tenant", "22174 Cushing Middle 2026-2027", "22174 Cushing"),
    ("binderkakos@gmail.com", "Debra Kakos", "tenant", "22727 Rein 2 Bed Larger 2027", "22727 Rein"),
    ("ellisonn@hotmail.com", "Nancy Ellison", "tenant", "1187 Park Avenue Unit 1 2026 May", "1187 Park Avenue"),
    ("conniehashope@gmail.com", "Connie Rosenbrook", "tenant", "1187 Park Avenue Unit 2 2026 May", "1187 Park Avenue"),
    ("rdc33542@gmail.com", "Robert Cole", "tenant", "1187 Park Avenue Unit 3 2026 May", "1187 Park Avenue"),
    ("charlesray2017@gmail.com", "Charles Ray", "handyman", None, None),
    ("info@oryx-horn.com", "Landlord", "landlord", None, None),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    # Existing deployments created `tickets` before photo_1/photo_2 existed.
    # CREATE TABLE IF NOT EXISTS above is a no-op for them, so add the columns
    # by hand if they're missing (data-preserving).
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)")}
    for col in ("photo_1", "photo_2"):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} TEXT")


def init_db():
    conn = get_conn()
    with conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        for email, name, role, lease_id, property_ in SEED_USERS:
            conn.execute(
                """
                INSERT INTO users (email, name, role, lease_id, property)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (email) DO NOTHING
                """,
                (email.lower(), name, role, lease_id, property_),
            )
    conn.close()


def get_user(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    conn.close()
    return row


def list_tenants():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users WHERE role = 'tenant' ORDER BY name").fetchall()
    conn.close()
    return rows


def add_tenant(email, name, lease_id, property_):
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO users (email, name, role, lease_id, property)
            VALUES (?, ?, 'tenant', ?, ?)
            ON CONFLICT (email) DO UPDATE SET name = excluded.name,
                                               lease_id = excluded.lease_id,
                                               property = excluded.property
            """,
            (email.lower().strip(), name, lease_id, property_),
        )
    conn.close()
