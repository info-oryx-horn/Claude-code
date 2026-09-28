# Tenant Maintenance Ticketing

A minimal maintenance-ticket tracker for a small rental portfolio: tenants submit issues, a
handyman works a single prioritized queue, and the landlord gets a status report.

## How it works

- **Login is email + a shared access code** — no per-person passwords. Enter the email on file
  plus the portfolio's access code and you're in. The code just keeps random internet traffic
  out; it's the same code for everyone (tenants, handyman, landlord), set via the `ACCESS_CODE`
  environment variable. If `ACCESS_CODE` isn't set (e.g. running locally), the code field
  disappears and login is email-only, same as before.
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

## Deploying to Render

The repo includes a `render.yaml` blueprint (at the repo root) that sets this up in one shot.

1. Push this repo to GitHub (already done if you're reading this from the branch).
2. In the [Render dashboard](https://dashboard.render.com), click **New > Blueprint** and point
   it at this GitHub repo. Render will find `render.yaml` and propose one web service
   (`upkeep`) with a 1GB persistent disk attached.
3. When prompted for the `ACCESS_CODE` environment variable, set it to whatever passphrase you
   want everyone (tenants, handyman, you) to enter alongside their email. `SECRET_KEY` is
   generated for you automatically.
4. Deploy. Render builds with `pip install -r requirements.txt` and runs
   `gunicorn app:app` — no code changes needed.
5. Share the resulting `*.onrender.com` URL (or a custom domain, set up separately in Render's
   dashboard) and the access code with your tenants and handyman.

**Why the persistent disk matters:** without it, the SQLite database (`ticketing.db`) lives on
the web service's ephemeral filesystem, which Render wipes on every redeploy and on free-tier
spin-down — you'd lose all tickets. The blueprint mounts a disk at `/var/data` and points
`DB_PATH` at it so ticket data survives redeploys and restarts. Persistent disks require a paid
plan (the blueprint requests `starter`); if Render's dashboard shows a different plan name by
the time you deploy, pick the cheapest paid plan — the Free plan doesn't support disks.

If you'd rather set it up by hand instead of using the blueprint: create a Web Service rooted at
`tenant_ticketing/`, build command `pip install -r requirements.txt`, start command
`gunicorn app:app`, add a disk mounted at `/var/data`, and set `DB_PATH=/var/data/ticketing.db`,
`ACCESS_CODE=<your code>`, and `SECRET_KEY=<random string>` as environment variables.

## Notes / next steps if you want more than "simple"

- The access code is a light deterrent, not real per-person authentication — anyone who has it
  can log in as any tenant by guessing/knowing their email. Move to magic-link email verification
  or per-tenant passwords if that stops being an acceptable tradeoff for this portfolio's size.
- The handyman queue is portfolio-wide (one shared priority order across all properties); split
  it by property if that's more useful once the portfolio grows.
