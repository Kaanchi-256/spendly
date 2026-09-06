"""Tests for the "Add Expense" feature (spec 07).

Written from `.claude/specs/07-add-expense.md` — the spec's Routes, Rules and
"Definition of done" — not from the route implementation.

Each test that inspects a profile provisions its own fresh user (unique email)
so assertions about totals / activity are deterministic against a shared DB
file. "Today" in the environment is 2026-09-06.
"""

import uuid

import pytest
from werkzeug.security import generate_password_hash

from database.db import get_db

TODAY = "2026-09-06"

CANONICAL_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------
def _make_user():
    email = f"add-exp-{uuid.uuid4().hex}@example.com"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Add Expense Person", email, generate_password_hash("password123")),
        )
        conn.commit()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()
    return uid


def _expenses_for(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def _count_all_expenses():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


@pytest.fixture
def fresh_user(client):
    """A logged-in client for a brand-new user that owns zero expenses.

    Yields (client, user_id).
    """
    uid = _make_user()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    return client, uid


VALID_FORM = {
    "amount": "250.75",
    "category": "Food",
    "date": TODAY,
    "description": "Lunch",
}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------
def test_get_add_expense_logged_out_redirects_to_login(client):
    """GET /expenses/add while logged out redirects to /login."""
    resp = client.get("/expenses/add")
    assert resp.status_code == 302, "unauthenticated GET must redirect"
    assert "/login" in resp.headers["Location"]


def test_post_add_expense_logged_out_redirects_to_login(client):
    """POST /expenses/add while logged out redirects to /login and inserts nothing."""
    before = _count_all_expenses()
    resp = client.post("/expenses/add", data=VALID_FORM)
    assert resp.status_code == 302, "unauthenticated POST must redirect"
    assert "/login" in resp.headers["Location"]
    assert _count_all_expenses() == before, "logged-out POST must not insert a row"


# ---------------------------------------------------------------------------
# GET renders the form
# ---------------------------------------------------------------------------
def test_get_renders_form_with_all_fields(fresh_user):
    """GET while logged in renders a form with amount, category, date, description."""
    c, _ = fresh_user
    resp = c.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="amount"' in body, "amount field present"
    assert 'name="category"' in body, "category field present"
    assert 'name="date"' in body, "date field present"
    assert 'name="description"' in body, "description field present"
    assert "<form" in body and 'method="post"' in body.lower()


def test_get_date_field_defaults_to_today(fresh_user):
    """The date field defaults to today's date."""
    c, _ = fresh_user
    body = c.get("/expenses/add").get_data(as_text=True)
    assert f'value="{TODAY}"' in body, "date input should be pre-filled with today"


def test_category_select_lists_exactly_canonical_categories(fresh_user):
    """The category <select> lists exactly the seven canonical categories."""
    c, _ = fresh_user
    body = c.get("/expenses/add").get_data(as_text=True)
    import re

    select_match = re.search(r"<select[^>]*name=[\"']category[\"'].*?</select>",
                             body, re.DOTALL | re.IGNORECASE)
    assert select_match, "a <select name='category'> must be rendered"
    options = re.findall(r"<option[^>]*value=[\"']([^\"']*)[\"']",
                         select_match.group(0), re.IGNORECASE)
    # drop an empty placeholder option if present
    options = [o for o in options if o != ""]
    assert options == CANONICAL_CATEGORIES, (
        f"category options must be exactly {CANONICAL_CATEGORIES}, got {options}"
    )


# ---------------------------------------------------------------------------
# Valid submission
# ---------------------------------------------------------------------------
def test_valid_submission_inserts_one_row_with_correct_values(fresh_user):
    """A valid submission inserts exactly one expenses row with the right values."""
    c, uid = fresh_user
    resp = c.post("/expenses/add", data={
        "amount": "250.75", "category": "Food",
        "date": TODAY, "description": "Lunch",
    })
    assert resp.status_code == 302, "successful add redirects"
    rows = _expenses_for(uid)
    assert len(rows) == 1, "exactly one row inserted"
    row = rows[0]
    assert row["user_id"] == uid
    assert row["amount"] == pytest.approx(250.75)
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Lunch"


def test_valid_submission_redirects_to_profile(fresh_user):
    """A valid submission redirects to /profile."""
    c, _ = fresh_user
    resp = c.post("/expenses/add", data=VALID_FORM)
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"], "must redirect to profile"


def test_valid_submission_shows_success_flash(fresh_user):
    """A valid submission shows a success flash on the resulting page."""
    c, _ = fresh_user
    resp = c.post("/expenses/add", data=VALID_FORM, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Expense added." in body, "success flash message shown"


def test_amount_rounded_to_two_decimals(fresh_user):
    """The stored amount is rounded to 2 decimal places."""
    c, uid = fresh_user
    c.post("/expenses/add", data={
        "amount": "10.129", "category": "Bills",
        "date": TODAY, "description": "",
    })
    rows = _expenses_for(uid)
    assert len(rows) == 1
    assert rows[0]["amount"] == pytest.approx(10.13)


# ---------------------------------------------------------------------------
# New expense reflected on /profile (no date filter)
# ---------------------------------------------------------------------------
def test_new_expense_appears_on_profile_all_sections(fresh_user):
    """The new expense appears in recent activity, count, total and breakdown."""
    c, _ = fresh_user
    c.post("/expenses/add", data={
        "amount": "300.00", "category": "Entertainment",
        "date": TODAY, "description": "Concert ticket",
    })
    body = c.get("/profile").get_data(as_text=True)
    assert "Concert ticket" in body, "recent activity lists the new expense"
    assert "Entertainment" in body, "category breakdown includes the new category"
    assert "₹300.00" in body, "total spent / breakdown reflects the amount"
    assert "1" in body, "transaction count reflects the single expense"


def test_second_expense_updates_profile_totals(fresh_user):
    """Adding a second expense updates the aggregate total on the profile."""
    c, _ = fresh_user
    c.post("/expenses/add", data={
        "amount": "100.00", "category": "Food", "date": TODAY, "description": "A",
    })
    c.post("/expenses/add", data={
        "amount": "50.50", "category": "Food", "date": TODAY, "description": "B",
    })
    body = c.get("/profile").get_data(as_text=True)
    assert "₹150.50" in body, "profile total sums both new expenses"


# ---------------------------------------------------------------------------
# Validation errors: re-render form (200), no row, values preserved
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad, why", [
    ({"amount": "", "category": "Food", "date": TODAY, "description": "x"},
     "missing amount"),
    ({"amount": "abc", "category": "Food", "date": TODAY, "description": "x"},
     "non-numeric amount"),
    ({"amount": "0", "category": "Food", "date": TODAY, "description": "x"},
     "amount is zero"),
    ({"amount": "-5", "category": "Food", "date": TODAY, "description": "x"},
     "negative amount"),
    ({"amount": "nan", "category": "Food", "date": TODAY, "description": "x"},
     "NaN amount"),
    ({"amount": "inf", "category": "Food", "date": TODAY, "description": "x"},
     "infinite amount"),
    ({"amount": "10", "category": "Groceries", "date": TODAY, "description": "x"},
     "category outside canonical list"),
    ({"amount": "10", "category": "", "date": TODAY, "description": "x"},
     "empty category"),
    ({"amount": "10", "category": "Food", "date": "not-a-date", "description": "x"},
     "unparseable date"),
    ({"amount": "10", "category": "Food", "date": "2026-13-40", "description": "x"},
     "impossible date"),
    ({"amount": "10", "category": "Food", "date": "", "description": "x"},
     "missing date"),
    ({"amount": "10", "category": "Food", "date": TODAY, "description": "z" * 201},
     "description longer than 200 chars"),
])
def test_invalid_submission_rerenders_and_inserts_nothing(fresh_user, bad, why):
    """Invalid submissions re-render the form (200) and insert no row."""
    c, uid = fresh_user
    resp = c.post("/expenses/add", data=bad)
    assert resp.status_code == 200, f"{why}: form must re-render, not redirect"
    assert _expenses_for(uid) == [], f"{why}: no expense row may be inserted"


@pytest.mark.parametrize("bad", [
    {"amount": "abc", "category": "Bills", "date": TODAY, "description": "Keep me"},
    {"amount": "-5", "category": "Health", "date": "2026-09-10", "description": "Also keep"},
])
def test_invalid_submission_preserves_entered_values(fresh_user, bad):
    """On a validation error the previously entered values are still shown."""
    c, _ = fresh_user
    body = c.post("/expenses/add", data=bad).get_data(as_text=True)
    assert bad["description"] in body, "description preserved"
    assert (f'value="{bad["category"]}"' in body
            or f'>{bad["category"]}<' in body), "category preserved / re-selected"
    # the submitted (bad) amount string is echoed back into the amount field
    assert bad["amount"] in body, "submitted amount echoed back"


def test_invalid_submission_shows_error_banner(fresh_user):
    """A validation failure renders an error message on the form."""
    c, _ = fresh_user
    body = c.post("/expenses/add", data={
        "amount": "0", "category": "Food", "date": TODAY, "description": "x",
    }).get_data(as_text=True)
    assert "error" in body.lower(), "an error banner/message should be shown"


# ---------------------------------------------------------------------------
# Blank description -> NULL
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("desc", ["", "   "])
def test_blank_description_stored_as_null(fresh_user, desc):
    """A blank/whitespace description is stored as SQL NULL, not ''."""
    c, uid = fresh_user
    c.post("/expenses/add", data={
        "amount": "42.00", "category": "Other", "date": TODAY, "description": desc,
    })
    rows = _expenses_for(uid)
    assert len(rows) == 1, "valid expense with blank description is accepted"
    assert rows[0]["description"] is None, "blank description must be NULL"


# ---------------------------------------------------------------------------
# Ownership: insert uses session user id, never a form-supplied user_id
# ---------------------------------------------------------------------------
def test_form_supplied_user_id_is_ignored(fresh_user):
    """A user cannot create an expense owned by another user via a form field."""
    c, uid = fresh_user
    other_uid = _make_user()
    c.post("/expenses/add", data={
        "amount": "77.00", "category": "Shopping", "date": TODAY,
        "description": "mine", "user_id": other_uid,
    })
    assert _expenses_for(other_uid) == [], "expense must not be assigned to other user"
    mine = _expenses_for(uid)
    assert len(mine) == 1 and mine[0]["user_id"] == uid, "expense owned by session user"


# ---------------------------------------------------------------------------
# Currency formatting on the new page
# ---------------------------------------------------------------------------
def test_add_expense_page_amounts_use_rupee_symbol(fresh_user):
    """Monetary amounts on the add-expense page render with the ₹ symbol."""
    c, _ = fresh_user
    body = c.get("/expenses/add").get_data(as_text=True)
    assert "₹" in body, "add-expense page should show the ₹ currency symbol"
