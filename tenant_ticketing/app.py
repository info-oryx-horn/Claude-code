import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, send_from_directory, session, url_for

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Shared passphrase everyone (tenants, handyman, landlord) enters alongside their
# email. Keeps random internet traffic out without building real password/account
# management. Unset locally -> login skips the check, so `python app.py` still
# works out of the box for development.
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")

# Overridable so a deployment can point uploaded ticket photos at a persistent
# disk, same as DB_PATH.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", db.DB_PATH.parent / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 2 photos, generous headroom


def _save_photo(file_storage):
    """Save an uploaded photo under a random name; return the filename or None."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        flash(f'"{file_storage.filename}" isn\'t a supported photo type and was skipped.')
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def _create_ticket(tenant, description, photo_1, photo_2):
    conn = db.get_conn()
    with conn:
        max_priority = conn.execute("SELECT MAX(priority) AS m FROM tickets").fetchone()["m"]
        next_priority = (max_priority or 0) + 1
        conn.execute(
            """
            INSERT INTO tickets
                (tenant_email, lease_id, property, description, status, priority, created_at, photo_1, photo_2)
            VALUES (?, ?, ?, ?, 'in_queue', ?, ?, ?, ?)
            """,
            (
                tenant["email"],
                tenant["lease_id"],
                tenant["property"],
                description,
                next_priority,
                db.now_iso(),
                photo_1,
                photo_2,
            ),
        )
    conn.close()


@app.before_request
def load_user():
    g.user = None
    email = session.get("email")
    if email:
        g.user = db.get_user(email)


def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            if roles and g.user["role"] not in roles:
                flash("You don't have access to that page.")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def parse_iso(value):
    return datetime.fromisoformat(value) if value else None


def format_duration(delta):
    if delta is None:
        return "-"
    hours = delta.total_seconds() / 3600
    if hours < 24:
        return f"{hours:.1f} hours"
    return f"{hours / 24:.1f} days"


@app.route("/")
def index():
    if g.user is None:
        return redirect(url_for("login"))
    if g.user["role"] == "tenant":
        return redirect(url_for("tenant_dashboard"))
    if g.user["role"] == "handyman":
        return redirect(url_for("handyman_dashboard"))
    return redirect(url_for("landlord_report"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        code = request.form.get("access_code", "").strip()
        if ACCESS_CODE and code != ACCESS_CODE:
            flash("That access code isn't right.")
            return redirect(url_for("login"))
        user = db.get_user(email)
        if user is None:
            flash("That email isn't set up yet. Ask your landlord to add you.")
            return redirect(url_for("login"))
        session["email"] = user["email"]
        return redirect(url_for("index"))
    return render_template("login.html", access_code_required=bool(ACCESS_CODE))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- tenant ---


@app.route("/tenant", methods=["GET"])
@login_required("tenant")
def tenant_dashboard():
    conn = db.get_conn()
    tickets = conn.execute(
        "SELECT * FROM tickets WHERE tenant_email = ? ORDER BY created_at DESC",
        (g.user["email"],),
    ).fetchall()
    conn.close()
    return render_template("tenant_dashboard.html", tickets=tickets)


@app.route("/tenant/tickets", methods=["POST"])
@login_required("tenant")
def create_ticket():
    description = request.form.get("description", "").strip()
    if not description:
        flash("Please describe the issue.")
        return redirect(url_for("tenant_dashboard"))

    photo_1 = _save_photo(request.files.get("photo_1"))
    photo_2 = _save_photo(request.files.get("photo_2"))
    _create_ticket(g.user, description, photo_1, photo_2)
    flash("Ticket submitted.")
    return redirect(url_for("tenant_dashboard"))


@app.route("/uploads/<path:filename>")
@login_required()
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ------------------------------------------------------------- handyman ---


@app.route("/handyman")
@login_required("handyman")
def handyman_dashboard():
    conn = db.get_conn()
    active = conn.execute(
        """
        SELECT tickets.*, users.name AS tenant_name
        FROM tickets JOIN users ON users.email = tickets.tenant_email
        WHERE status != 'complete'
        ORDER BY priority ASC
        """
    ).fetchall()
    completed = conn.execute(
        """
        SELECT tickets.*, users.name AS tenant_name
        FROM tickets JOIN users ON users.email = tickets.tenant_email
        WHERE status = 'complete'
        ORDER BY completed_at DESC
        LIMIT 25
        """
    ).fetchall()
    conn.close()
    return render_template("handyman_dashboard.html", active=active, completed=completed)


@app.route("/handyman/tickets/<int:ticket_id>/status", methods=["POST"])
@login_required("handyman")
def update_status(ticket_id):
    new_status = request.form.get("status")
    if new_status not in ("in_queue", "in_process", "complete"):
        flash("Unknown status.")
        return redirect(url_for("handyman_dashboard"))

    conn = db.get_conn()
    with conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            conn.close()
            flash("Ticket not found.")
            return redirect(url_for("handyman_dashboard"))

        updates = {"status": new_status}
        if new_status == "in_process" and ticket["started_at"] is None:
            updates["started_at"] = db.now_iso()
        if new_status == "complete" and ticket["completed_at"] is None:
            updates["completed_at"] = db.now_iso()
        if new_status == "in_queue":
            updates["started_at"] = None
            updates["completed_at"] = None

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = ?",
            (*updates.values(), ticket_id),
        )
    conn.close()
    return redirect(url_for("handyman_dashboard"))


@app.route("/handyman/tickets/<int:ticket_id>/move", methods=["POST"])
@login_required("handyman")
def move_ticket(ticket_id):
    direction = request.form.get("direction")
    conn = db.get_conn()
    with conn:
        current = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if current is None:
            conn.close()
            return redirect(url_for("handyman_dashboard"))

        if direction == "up":
            neighbor = conn.execute(
                "SELECT * FROM tickets WHERE priority < ? AND status != 'complete' ORDER BY priority DESC LIMIT 1",
                (current["priority"],),
            ).fetchone()
        else:
            neighbor = conn.execute(
                "SELECT * FROM tickets WHERE priority > ? AND status != 'complete' ORDER BY priority ASC LIMIT 1",
                (current["priority"],),
            ).fetchone()

        if neighbor is not None:
            conn.execute("UPDATE tickets SET priority = ? WHERE id = ?", (neighbor["priority"], current["id"]))
            conn.execute("UPDATE tickets SET priority = ? WHERE id = ?", (current["priority"], neighbor["id"]))
    conn.close()
    return redirect(url_for("handyman_dashboard"))


# ------------------------------------------------------------- landlord ---


@app.route("/landlord")
@login_required("landlord")
def landlord_report():
    conn = db.get_conn()
    tickets = conn.execute(
        """
        SELECT tickets.*, users.name AS tenant_name
        FROM tickets JOIN users ON users.email = tickets.tenant_email
        ORDER BY created_at DESC
        """
    ).fetchall()
    conn.close()

    counts = {"in_queue": 0, "in_process": 0, "complete": 0}
    resolution_deltas = []
    response_deltas = []
    for t in tickets:
        counts[t["status"]] += 1
        created = parse_iso(t["created_at"])
        if t["completed_at"]:
            resolution_deltas.append(parse_iso(t["completed_at"]) - created)
        if t["started_at"]:
            response_deltas.append(parse_iso(t["started_at"]) - created)

    avg_resolution = (
        sum(resolution_deltas, start=resolution_deltas[0]) / len(resolution_deltas)
        if resolution_deltas
        else None
    )
    avg_response = (
        sum(response_deltas, start=response_deltas[0]) / len(response_deltas)
        if response_deltas
        else None
    )

    stats = {
        "total": len(tickets),
        "in_queue": counts["in_queue"],
        "in_process": counts["in_process"],
        "complete": counts["complete"],
        "avg_resolution": format_duration(avg_resolution),
        "avg_response": format_duration(avg_response),
    }
    tenants = db.list_tenants()
    return render_template("landlord_report.html", tickets=tickets, stats=stats, tenants=tenants)


@app.route("/landlord/tickets", methods=["POST"])
@login_required("landlord")
def create_ticket_for_tenant():
    tenant_email = request.form.get("tenant_email", "").strip().lower()
    description = request.form.get("description", "").strip()
    tenant = db.get_user(tenant_email)

    if tenant is None or tenant["role"] != "tenant":
        flash("Pick a tenant from the list.")
        return redirect(url_for("landlord_report"))
    if not description:
        flash("Please describe the issue.")
        return redirect(url_for("landlord_report"))

    photo_1 = _save_photo(request.files.get("photo_1"))
    photo_2 = _save_photo(request.files.get("photo_2"))
    _create_ticket(tenant, description, photo_1, photo_2)
    flash(f"Ticket logged for {tenant['name']}.")
    return redirect(url_for("landlord_report"))


@app.route("/landlord/tenants", methods=["POST"])
@login_required("landlord")
def add_tenant():
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    lease_id = request.form.get("lease_id", "").strip()
    property_ = request.form.get("property", "").strip()

    if not email or not name:
        flash("Email and name are required.")
        return redirect(url_for("landlord_report"))

    db.add_tenant(email, name, lease_id or None, property_ or None)
    flash(f"{name} can now log in with {email}.")
    return redirect(url_for("landlord_report"))


with app.app_context():
    db.init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
