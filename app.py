import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# A real, secret value must be set via the SECRET_KEY env var in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #

def current_user():
    """Return the logged-in user row (or None) based on the session."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.template_filter("inr")
def inr(value):
    """Format a number as an INR amount, e.g. 6120.5 -> '₹6,120.50'."""
    return f"₹{value or 0:,.2f}"


def _format_join_date(value):
    """Turn a stored 'YYYY-MM-DD HH:MM:SS' string into '1 September 2026'."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


@app.template_filter("expense_date")
def expense_date(value):
    """Format a stored ISO 'YYYY-MM-DD' date as '2 Sep 2026'."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return value
    return f"{parsed.day} {parsed.strftime('%b %Y')}"


def _parse_iso_date(value):
    """Return a date from a 'YYYY-MM-DD' string, or None if it doesn't parse."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _pretty_date(value):
    """Format a date as '2 Sep 2026', matching the expense_date filter style."""
    return f"{value.day} {value.strftime('%b %Y')}"


def _resolve_date_range(args):
    """Resolve profile filter args into (start, end, label) ISO date strings.

    A named ``range`` (this-month / last-30-days / all) takes precedence over
    explicit ``start`` / ``end`` values. Unparseable bounds are dropped. If
    both bounds are present and reversed, they are swapped. Returns
    ``(None, None, "All time")`` when nothing valid is supplied.
    """
    named = args.get("range", "")
    today = date.today()

    if named == "this-month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), "This month"
    if named == "last-30-days":
        start = today - timedelta(days=29)
        return start.isoformat(), today.isoformat(), "Last 30 days"
    if named:  # "all" or anything unrecognised
        return None, None, "All time"

    start = _parse_iso_date(args.get("start", ""))
    end = _parse_iso_date(args.get("end", ""))
    if start and end and start > end:
        start, end = end, start

    if start and end:
        label = f"{_pretty_date(start)} – {_pretty_date(end)}"
    elif start:
        label = f"Since {_pretty_date(start)}"
    elif end:
        label = f"Up to {_pretty_date(end)}"
    else:
        label = "All time"

    return (
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        label,
    )


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name:
        error = "Please enter your name."
    elif len(name) > 100:
        error = "Name is too long."
    elif "@" not in email or "." not in email.split("@")[-1]:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm_password:
        error = "Passwords do not match."
    else:
        error = None

    if error:
        return render_template("register.html", error=error, name=name, email=email)

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return render_template(
                "register.html",
                error="An account with that email already exists.",
                name=name,
                email=email,
            )
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )
    finally:
        conn.close()

    flash("Account created — please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    error = "Incorrect email or password."

    if not email or not password:
        return render_template("login.html", error=error, email=email)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error=error, email=email)

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    start, end, range_label = _resolve_date_range(request.args)

    clauses = ["user_id = ?"]
    params = [user["id"]]
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    where = " AND ".join(clauses)

    conn = get_db()
    try:
        totals = conn.execute(
            f"SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            f"FROM expenses WHERE {where}",
            params,
        ).fetchone()
        category_rows = conn.execute(
            f"SELECT category, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            f"FROM expenses WHERE {where} GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()
        recent_rows = conn.execute(
            f"SELECT date, description, category, amount "
            f"FROM expenses WHERE {where} "
            f"ORDER BY date DESC, id DESC LIMIT 10",
            params,
        ).fetchall()
    finally:
        conn.close()

    max_total = category_rows[0]["total"] if category_rows else 0
    top_category = category_rows[0]["category"] if category_rows else None
    categories = [
        {
            "category": row["category"],
            "n": row["n"],
            "total": row["total"],
            "pct": round(row["total"] / max_total * 100) if max_total else 0,
        }
        for row in category_rows
    ]

    recent_expenses = [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in recent_rows
    ]

    return render_template(
        "profile.html",
        user=user,
        joined=_format_join_date(user["created_at"]),
        expense_count=totals["n"],
        total_spent=totals["total"],
        top_category=top_category,
        categories=categories,
        recent_expenses=recent_expenses,
        start=start or "",
        end=end or "",
        range_label=range_label,
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
