# Tenant Maintenance Ticketing

A minimal maintenance-ticket tracker for a small rental portfolio: tenants submit issues, a
handyman works a single prioritized queue, and the landlord gets a status report.

## How it works

- **Login is email-only** — no passwords. Enter the email on file and you're in. This keeps
  things simple for a small, trusted portfolio; it is not meant for a public-facing property
  manager site.
- **Tenants** submit a text description of an issue and see the status of their own tickets
  (`In Queue` / `In Process` / `Complete`).
- **Handyman** (`charlesray2017@gmail.com`) sees every open ticket in one prioritized list,
  reorders it with the up/down arrows, and advances each ticket through its status.
- **Landlord** (`info@oryx-horn.com`) sees ticket counts by status, average time-to-start,
  average time-to-resolution, and the full ticket log. New tenants are added from this page —
  as soon as a tenant is added, they can log in with that email.

Roles and the initial tenant roster are seeded from the lease roll into `db.py` on first run.

## Run it

```bash
cd tenant_ticketing
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000` and log in as any of:
- A tenant email from the lease roll (e.g. `garyrunion67@gmail.com`)
- The handyman: `charlesray2017@gmail.com`
- The landlord: `info@oryx-horn.com`

Data is stored in `ticketing.db` (SQLite), created automatically on first run.

## Notes / next steps if you want more than "simple"

- Add a real auth step (magic link email or a password) before putting this on the open internet.
- The handyman queue is portfolio-wide (one shared priority order across all properties); split
  it by property if that's more useful once the portfolio grows.
- `SECRET_KEY` should be set via environment variable in any real deployment.
