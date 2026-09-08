"""Tests for the "Add Expense" feature (spec 07).

Derived from `.claude/specs/07-add-expense.md` — the documented expected
behaviour and "Definition of done" checklist — not from the route
implementation. Each test that inspects a profile provisions its own fresh
user with a unique email, because the DB is a shared file across the session.
"""

import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from database.db import get_db

ADD_URL = "/expenses/add"
PROFILE_URL = "/profile"
LOGIN_URL = "/login"

CANONICAL_CATEGORIES = (
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
)

TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------
def _make_user():
    email = f"add-{uuid.uuid4().hex}@example.com"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Adder Person", email, generate_password_hash("password123")),
        )
        conn.commit()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()
    return uid


def _rows_for(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT amount, category, date, description, user_id "
            "FROM expenses WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def _count_all_expenses():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    finally:
        conn.close()


@pytest.fixture
def fresh_user(client):
    """Return (client, user_id) for a brand-new logged-in user with no expenses."""
    uid = _make_user()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    return client, uid


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------
def test_get_add_expense_logged_out_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess.clear()
    resp = client.get(ADD_URL)
    assert resp.status_code == 302, "GET /expenses/add must require auth"
    assert LOGIN_URL in resp.headers["Location"]


def test_post_add_expense_logged_out_redirects_and_inserts_nothing(client):
    with client.session_transaction() as sess:
        sess.clear()
    before = _count_all_expenses()
    resp = client.post(ADD_URL, data={
        "amount": "50", "category": "Food", "date": TODAY, "description": "x",
    })
    assert resp.status_code == 302, "POST /expenses/add must require auth"
    assert LOGIN_URL in resp.headers["Location"]
    assert _count_all_expenses() == before, "no row inserted for a logged-out POST"


# ---------------------------------------------------------------------------
# GET renders the form
# ---------------------------------------------------------------------------
def test_get_renders_form_with_all_fields(fresh_user):
    client, _ = fresh_user
    body = client.get(ADD_URL).get_data(as_text=True)
    assert 'name="amount"' in body, "amount field present"
    assert 'name="category"' in body, "category field present"
    assert 'name="date"' in body, "date field present"
    assert 'name="description"' in body, "description field present"
    assert f'action="{ADD_URL}"' in body or "<form" in body, "form posts to add_expense"


def test_get_date_field_defaults_to_today(fresh_user):
    client, _ = fresh_user
    body = client.get(ADD_URL).get_data(as_text=True)
    assert f'value="{TODAY}"' in body, "date input defaults to today's ISO date"


def test_get_category_select_lists_exactly_canonical_categories(fresh_user):
    client, _ = fresh_user
    body = client.get(ADD_URL).get_data(as_text=True)
    for cat in CANONICAL_CATEGORIES:
        assert f">{cat}<" in body or f'value="{cat}"' in body, f"{cat} option present"
    # nothing outside the canonical set
    for bogus in ("Groceries", "Rent", "Travel", "Misc"):
        assert f'value="{bogus}"' not in body, f"{bogus} must not be an option"


def test_add_expense_page_shows_rupee_symbol(fresh_user):
    client, _ = fresh_user
    body = client.get(ADD_URL).get_data(as_text=True)
    assert "₹" in body, "the add-expense page renders the ₹ symbol"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_valid_submission_inserts_one_row_and_redirects(fresh_user):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "250.75", "category": "Food",
        "date": TODAY, "description": "Lunch",
    })
    assert resp.status_code == 302, "successful add redirects"
    assert PROFILE_URL in resp.headers["Location"], "redirect target is /profile"

    rows = _rows_for(uid)
    assert len(rows) == 1, "exactly one row inserted"
    row = rows[0]
    assert row["user_id"] == uid
    assert row["amount"] == pytest.approx(250.75)
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Lunch"


def test_valid_submission_shows_success_flash(fresh_user):
    client, _ = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "10", "category": "Bills", "date": TODAY, "description": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Expense added." in resp.get_data(as_text=True), "success flash shown"


def test_amount_is_rounded_to_two_decimals(fresh_user):
    client, uid = fresh_user
    client.post(ADD_URL, data={
        "amount": "10.129", "category": "Other", "date": TODAY, "description": "r",
    })
    assert _rows_for(uid)[0]["amount"] == pytest.approx(10.13), "stored amount rounded to 2dp"


def test_new_expense_reflected_in_all_profile_sections(fresh_user):
    client, _ = fresh_user
    client.post(ADD_URL, data={
        "amount": "1234.00", "category": "Entertainment",
        "date": TODAY, "description": "Concert tickets",
    })
    body = client.get(PROFILE_URL).get_data(as_text=True)
    assert "Concert tickets" in body, "appears in recent activity"
    assert "₹1,234.00" in body, "counts toward total spent"
    assert "Entertainment" in body, "appears in category breakdown"
    assert "1" in body, "transaction count includes the new expense"


@pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
def test_every_canonical_category_accepted(fresh_user, category):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "5", "category": category, "date": TODAY, "description": "",
    })
    assert resp.status_code == 302, f"{category} is a valid category"
    assert _rows_for(uid)[0]["category"] == category


# ---------------------------------------------------------------------------
# Description handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("description", ["", "   ", "\t  \n"])
def test_blank_or_whitespace_description_stored_as_null(fresh_user, description):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "12", "category": "Food", "date": TODAY, "description": description,
    })
    assert resp.status_code == 302
    assert _rows_for(uid)[0]["description"] is None, "blank description stored as NULL"


def test_description_over_200_chars_trimmed_to_200(fresh_user):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "12", "category": "Food", "date": TODAY,
        "description": "x" * 201,
    })
    assert resp.status_code == 302, "over-long description is trimmed, not rejected"
    assert _rows_for(uid)[0]["description"] == "x" * 200, "description trimmed to 200 chars"


def test_description_exactly_200_chars_accepted(fresh_user):
    client, uid = fresh_user
    desc = "y" * 200
    resp = client.post(ADD_URL, data={
        "amount": "12", "category": "Food", "date": TODAY, "description": desc,
    })
    assert resp.status_code == 302, "200-char description is within the limit"
    assert _rows_for(uid)[0]["description"] == desc


# ---------------------------------------------------------------------------
# Validation errors — each re-renders at 200 with no row inserted
# ---------------------------------------------------------------------------
# label -> extra form data to merge over the valid baseline (amount omitted == "missing")
INVALID_AMOUNTS = {
    "missing": {},
    "empty": {"amount": ""},
    "whitespace": {"amount": "   "},
    "non_numeric": {"amount": "abc"},
    "zero": {"amount": "0"},
    "zero_decimal": {"amount": "0.00"},
    "negative": {"amount": "-5"},
    "nan": {"amount": "nan"},
    "inf": {"amount": "inf"},
    "negative_inf": {"amount": "-inf"},
}


@pytest.mark.parametrize("label", list(INVALID_AMOUNTS))
def test_invalid_amount_rejected(fresh_user, label):
    client, uid = fresh_user
    data = {"category": "Food", "date": TODAY, "description": "d"}
    data.update(INVALID_AMOUNTS[label])
    resp = client.post(ADD_URL, data=data)
    assert resp.status_code == 200, f"{label} amount must re-render the form"
    assert _rows_for(uid) == [], f"{label} amount must not insert a row"


@pytest.mark.parametrize("category", ["", "   ", "Groceries", "food", "FOOD", "Rent", "Unknown"])
def test_non_canonical_or_empty_category_rejected(fresh_user, category):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "20", "category": category, "date": TODAY, "description": "d",
    })
    assert resp.status_code == 200, f"category {category!r} must be rejected"
    assert _rows_for(uid) == [], f"category {category!r} must not be stored"


@pytest.mark.parametrize("bad_date", [
    "", "not-a-date", "2026/09/08", "08-09-2026",
    "2026-13-01", "2026-02-30", "2026-00-10", "20260908",
])
def test_invalid_or_missing_date_rejected(fresh_user, bad_date):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "20", "category": "Food", "date": bad_date, "description": "d",
    })
    assert resp.status_code == 200, f"date {bad_date!r} must be rejected"
    assert _rows_for(uid) == [], f"date {bad_date!r} must not insert a row"


def test_missing_date_field_rejected(fresh_user):
    client, uid = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "20", "category": "Food", "description": "d",
    })
    assert resp.status_code == 200, "an absent date field must be rejected"
    assert _rows_for(uid) == [], "no row inserted when date is missing"


# ---------------------------------------------------------------------------
# Entered values preserved on validation error
# ---------------------------------------------------------------------------
def test_entered_values_preserved_on_error(fresh_user):
    client, _ = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "0",  # invalid -> triggers re-render
        "category": "Shopping",
        "date": "2026-03-15",
        "description": "Sneakers",
    })
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'value="0"' in body, "amount preserved"
    assert "Sneakers" in body, "description preserved"
    assert "2026-03-15" in body, "date preserved"
    assert "Shopping" in body, "category preserved / re-selected"


def test_validation_error_shows_error_banner(fresh_user):
    client, _ = fresh_user
    resp = client.post(ADD_URL, data={
        "amount": "abc", "category": "Food", "date": TODAY, "description": "",
    })
    body = resp.get_data(as_text=True).lower()
    assert resp.status_code == 200
    assert "error" in body or "amount" in body, "an error message is displayed"


# ---------------------------------------------------------------------------
# Ownership — form-supplied user_id is ignored
# ---------------------------------------------------------------------------
def test_form_supplied_user_id_is_ignored(client):
    victim = _make_user()
    attacker = _make_user()
    with client.session_transaction() as sess:
        sess["user_id"] = attacker
    resp = client.post(ADD_URL, data={
        "amount": "99", "category": "Food", "date": TODAY,
        "description": "not yours", "user_id": victim, "id": victim,
    })
    assert resp.status_code == 302
    assert _rows_for(victim) == [], "victim must not receive the expense"
    attacker_rows = _rows_for(attacker)
    assert len(attacker_rows) == 1, "expense is owned by the session user"
    assert attacker_rows[0]["user_id"] == attacker
