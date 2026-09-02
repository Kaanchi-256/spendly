import os
import tempfile

import pytest

# Point the DB at a throwaway file BEFORE importing the app: app.py runs
# init_db() + seed_db() at import time, and get_db() reads SPENDLY_DB_PATH.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SPENDLY_DB_PATH"] = _tmp.name

from app import app as flask_app            # noqa: E402
from database.db import init_db, seed_db    # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    # The app import already seeded; re-run defensively. Both are idempotent:
    # init_db() uses CREATE TABLE IF NOT EXISTS, seed_db() early-returns when
    # users already exist.
    with flask_app.app_context():
        init_db()
        seed_db()
    yield
    try:
        os.unlink(_tmp.name)
    except OSError:
        pass


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_user_id():
    from database.db import get_db

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
    finally:
        conn.close()
    return row["id"]


@pytest.fixture
def auth_client(client):
    """A test client with a logged-in session (the seeded demo user)."""
    with client.session_transaction() as sess:
        sess["user_id"] = _seed_user_id()
    return client
