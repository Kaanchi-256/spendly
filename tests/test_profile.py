import uuid

from database.db import get_db

SEED_CATEGORIES = [
    "Shopping", "Bills", "Health", "Food", "Entertainment", "Other", "Transport",
]


def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_shows_seed_user_data(auth_client):
    resp = auth_client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹6,120.50" in body          # total spent, actual seed data


def test_profile_top_category_is_shopping(auth_client):
    body = auth_client.get("/profile").get_data(as_text=True)
    i = body.index("Top category")
    assert "Shopping" in body[i:i + 200]


def test_profile_renders_transaction_rows_newest_first(auth_client):
    body = auth_client.get("/profile").get_data(as_text=True)
    assert 'class="profile-table"' in body
    assert "Groceries" in body
    assert "New shoes" in body
    # "New shoes" is day 15, "Groceries" is day 2 -> newest first
    assert body.index("New shoes") < body.index("Groceries")


def test_profile_category_breakdown_has_seven_categories(auth_client):
    body = auth_client.get("/profile").get_data(as_text=True)
    for cat in SEED_CATEGORIES:
        assert cat in body


def test_fresh_user_sees_empty_state(client):
    email = f"new-{uuid.uuid4().hex}@example.com"
    client.post(
        "/register",
        data={
            "name": "Fresh Person",
            "email": email,
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    conn = get_db()
    try:
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Fresh Person" in body
    assert "No activity yet." in body           # recent-activity empty state
    assert "No expenses logged yet." in body    # category empty state
    assert "₹0.00" in body                 # total spent is zero
