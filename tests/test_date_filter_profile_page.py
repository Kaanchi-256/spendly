"""Tests for the /profile date-range filter (spec 06).

Derived from the spec's expected behaviour and "Definition of done" checklist,
not from the implementation. Each test provisions its own fresh user with
expenses on fixed known dates, because the seed data lives in the current
calendar month and would make date-window assertions non-deterministic.
"""

import uuid

import pytest

from database.db import get_db

# "Today" per the environment is 2026-09-04. Named-range tests assume the
# current month is September 2026.
CURRENT_MONTH_PREFIX = "2026-09"

# amount, category, date (ISO), description
STANDARD_EXPENSES = [
    (100.00, "Food", "2026-01-05", "Jan lunch"),
    (50.00, "Transport", "2026-01-20", "Jan bus"),
    (200.00, "Shopping", "2026-02-10", "Feb shirt"),
    (300.00, "Bills", "2026-09-02", "Sep bill"),
]


def _register_user():
    email = f"filter-{uuid.uuid4().hex}@example.com"
    conn = get_db()
    try:
        from werkzeug.security import generate_password_hash

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Filter Person", email, generate_password_hash("password123")),
        )
        conn.commit()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()
    return uid


def _insert_expenses(user_id, rows):
    conn = get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amount, category, date, description)
             for amount, category, date, description in rows],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def user_client(client):
    """Factory: given a list of expense rows, return a logged-in client whose
    user owns exactly those expenses."""

    def _make(rows):
        uid = _register_user()
        if rows:
            _insert_expenses(uid, rows)
        with client.session_transaction() as sess:
            sess["user_id"] = uid
        return client

    return _make


@pytest.fixture
def standard_client(user_client):
    return user_client(STANDARD_EXPENSES)


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------
def test_profile_filter_requires_login(client):
    resp = client.get("/profile?start=2026-01-01&end=2026-01-31")
    assert resp.status_code == 302, "filtered /profile must require auth"
    assert "/login" in resp.headers["Location"]


# --------------------------------------------------------------------------
# No params => all-time / unfiltered
# --------------------------------------------------------------------------
def test_no_params_shows_all_time_totals(standard_client):
    body = standard_client.get("/profile").get_data(as_text=True)
    assert "₹650.00" in body, "all-time total of the 4 fixed expenses"
    for desc in ("Jan lunch", "Jan bus", "Feb shirt", "Sep bill"):
        assert desc in body, f"{desc} should appear in unfiltered activity"


# --------------------------------------------------------------------------
# Custom start/end window
# --------------------------------------------------------------------------
def test_start_end_restricts_every_section(standard_client):
    body = standard_client.get(
        "/profile?start=2026-01-01&end=2026-01-31"
    ).get_data(as_text=True)
    assert "₹150.00" in body, "only the two January expenses count"
    assert "Jan lunch" in body and "Jan bus" in body
    assert "Feb shirt" not in body, "Feb expense is outside the window"
    assert "Sep bill" not in body, "Sep expense is outside the window"
    # category breakdown is recomputed from the filtered rows
    assert "Shopping" not in body, "Shopping only appears in the Feb expense"


def test_bounds_are_inclusive(standard_client):
    # window edges land exactly on expense dates
    body = standard_client.get(
        "/profile?start=2026-01-05&end=2026-01-20"
    ).get_data(as_text=True)
    assert "Jan lunch" in body, "start bound is inclusive (date >= start)"
    assert "Jan bus" in body, "end bound is inclusive (date <= end)"
    assert "₹150.00" in body


def test_end_only_window(standard_client):
    body = standard_client.get(
        "/profile?end=2026-02-28"
    ).get_data(as_text=True)
    assert "₹350.00" in body, "Jan + Feb expenses, Sep excluded"
    assert "Sep bill" not in body


# --------------------------------------------------------------------------
# Unparseable bounds are ignored (no error)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("qs", [
    "start=not-a-date",
    "start=2026-13-40",
    "end=garbage",
    "start=&end=",
])
def test_unparseable_bounds_do_not_error(standard_client, qs):
    resp = standard_client.get(f"/profile?{qs}")
    assert resp.status_code == 200, f"{qs} must be ignored, not error"
    body = resp.get_data(as_text=True)
    assert "₹650.00" in body, "ignored bound => all-time total unchanged"


def test_unparseable_start_keeps_valid_end(standard_client):
    body = standard_client.get(
        "/profile?start=not-a-date&end=2026-01-31"
    ).get_data(as_text=True)
    # start ignored, end still applied -> January only
    assert "₹150.00" in body
    assert "Feb shirt" not in body


# --------------------------------------------------------------------------
# start > end => swapped
# --------------------------------------------------------------------------
def test_reversed_bounds_are_swapped(standard_client):
    body = standard_client.get(
        "/profile?start=2026-02-28&end=2026-01-01"
    ).get_data(as_text=True)
    # treated as 2026-01-01 .. 2026-02-28
    assert "₹350.00" in body, "Jan + Feb expenses after swap"
    assert "Jan lunch" in body and "Feb shirt" in body
    assert "Sep bill" not in body


# --------------------------------------------------------------------------
# range presets take precedence over start/end
# --------------------------------------------------------------------------
def test_range_all_clears_filter(standard_client):
    body = standard_client.get(
        "/profile?range=all&start=2026-01-01&end=2026-01-02"
    ).get_data(as_text=True)
    assert "₹650.00" in body, "range=all overrides start/end -> all-time"
    assert "Feb shirt" in body and "Sep bill" in body


def test_range_this_month(standard_client):
    body = standard_client.get(
        "/profile?range=this-month&start=2026-01-01&end=2026-01-31"
    ).get_data(as_text=True)
    assert "₹300.00" in body, "only the Sep expense is in the current month"
    assert "Sep bill" in body
    assert "Jan lunch" not in body, "range preset overrides start/end"


def test_range_last_30_days(standard_client):
    body = standard_client.get(
        "/profile?range=last-30-days"
    ).get_data(as_text=True)
    assert "₹300.00" in body, "only Sep 2 expense falls in the last 30 days"
    assert "Sep bill" in body
    assert "Feb shirt" not in body


# --------------------------------------------------------------------------
# Empty filtered result => empty states, not a crash
# --------------------------------------------------------------------------
def test_empty_window_renders_empty_states(standard_client):
    resp = standard_client.get("/profile?start=2020-01-01&end=2020-12-31")
    assert resp.status_code == 200, "empty result must not raise"
    body = resp.get_data(as_text=True)
    assert "₹0.00" in body, "empty window => zero total"
    assert "No activity yet." in body, "recent-activity empty state"
    assert "No expenses logged yet." in body, "category breakdown empty state"


def test_empty_window_shows_zero_transactions(standard_client):
    body = standard_client.get(
        "/profile?start=2020-01-01&end=2020-01-02"
    ).get_data(as_text=True)
    assert "0" in body
    for desc in ("Jan lunch", "Jan bus", "Feb shirt", "Sep bill"):
        assert desc not in body, "no expense rows in an empty window"


# --------------------------------------------------------------------------
# Date inputs pre-filled with the active window
# --------------------------------------------------------------------------
def test_date_inputs_prefilled_after_filtering(standard_client):
    body = standard_client.get(
        "/profile?start=2026-01-01&end=2026-01-31"
    ).get_data(as_text=True)
    assert 'value="2026-01-01"' in body, "start input pre-filled"
    assert 'value="2026-01-31"' in body, "end input pre-filled"


# --------------------------------------------------------------------------
# Recent-activity table keeps LIMIT 10
# --------------------------------------------------------------------------
def test_recent_activity_limited_to_10_within_window(user_client):
    rows = [
        (10.00 + i, "Food", f"2026-03-{i + 1:02d}", f"bulk-{i:02d}")
        for i in range(12)
    ]
    c = user_client(rows)
    body = c.get(
        "/profile?start=2026-03-01&end=2026-03-31"
    ).get_data(as_text=True)
    shown = [f"bulk-{i:02d}" for i in range(12) if f"bulk-{i:02d}" in body]
    assert len(shown) == 10, f"activity table capped at 10 rows, got {len(shown)}"


def test_summary_count_reflects_full_window_not_table_limit(user_client):
    rows = [
        (10.00, "Food", f"2026-03-{i + 1:02d}", f"bulk-{i:02d}")
        for i in range(12)
    ]
    c = user_client(rows)
    body = c.get(
        "/profile?start=2026-03-01&end=2026-03-31"
    ).get_data(as_text=True)
    assert "12" in body, "transaction count uses all 12 filtered rows"
    assert "₹120.00" in body, "summary total sums all 12 filtered rows"


# --------------------------------------------------------------------------
# Currency formatting preserved
# --------------------------------------------------------------------------
def test_amounts_use_rupee_symbol_when_filtered(standard_client):
    body = standard_client.get(
        "/profile?start=2026-01-01&end=2026-12-31"
    ).get_data(as_text=True)
    assert "₹" in body, "amounts still rendered with the ₹ symbol"
