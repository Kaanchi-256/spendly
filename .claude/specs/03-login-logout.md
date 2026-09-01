# Spec: Login and Logout

## Overview
This feature makes the auth flow functional by adding session-based login and logout.
Currently `GET /login` renders `login.html` but the form `POST` has no handler, and
`/logout` returns the placeholder string "Logout — coming in Step 3". This step adds
`POST /login` (look up the user by email, verify the password hash with werkzeug, and
store `user_id` in the Flask session), a real `GET /logout` (clear the session and
redirect to the landing page), and a `current_user` helper plus a `login_required`
decorator so later steps (profile, expense CRUD) can protect their routes. It also wires
the navbar in `base.html` to show "Sign in / Get started" when logged out and
"Profile / Sign out" when logged in. This is the gate that every logged-in page in
Spendly depends on.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`) — complete.
- Step 2 — Registration (`POST /register` creating hashed users) — complete. Login needs
  real user rows with valid `password_hash` values to authenticate against.

## Routes
- `GET /login` — render the sign-in form — public *(already exists, unchanged)*
- `POST /login` — validate email/password, verify the werkzeug hash, set
  `session["user_id"]` on success and redirect to `/profile`; re-render `login.html` with
  an `error` on failure — public *(new handler on the existing route)*
- `GET /logout` — clear the session and redirect to `/` with a flashed confirmation —
  logged-in (harmless if called while logged out) *(replaces the placeholder string)*

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE,
`password_hash`, `created_at`) already has everything needed to authenticate. Verified
against `database/db.py`.

## Templates
- Create: none.
- Modify:
  - `templates/login.html` — no structural change required; it already renders an
    `{{ error }}` block and posts `email` / `password` to `/login`. Optionally repopulate
    the `email` field from a `form`/`email` value on failure (nice-to-have).
  - `templates/base.html` — make the `.nav-links` block conditional on
    `current_user`: show `Profile` + `Sign out` (`url_for('logout')`) when logged in,
    otherwise the existing `Sign in` + `Get started` links.

## Files
- `app.py` —
  - Import `session` from `flask` and `check_password_hash` from `werkzeug.security`.
  - Add a `current_user()` helper that returns the logged-in user row (or `None`) by
    reading `session.get("user_id")`, and expose it to all templates via
    `@app.context_processor`.
  - Add a `login_required` decorator (redirects to `/login` when there is no session
    user) for use by later steps.
  - Implement the `POST` branch of the `login` view.
  - Replace the `logout` placeholder with a real implementation
    (`session.clear()` + redirect).
- `templates/base.html` — conditional nav links (see Templates).

## Files to create
None.

## New dependencies
No new dependencies. `flask` and `werkzeug` are already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw `sqlite3`.
- Parameterised queries only — never string-format values into SQL.
- Passwords hashed with werkzeug — verify with `check_password_hash(row["password_hash"],
  password)`; never compare plaintext.
- Use CSS variables — never hardcode hex values (reuse existing nav classes; no new
  colours).
- All templates extend `base.html`.
- Server-side validation is authoritative:
  - `email` — required, trimmed, lowercased before lookup (matches how registration
    stores it).
  - `password` — required, non-empty.
- Use a single generic error ("Incorrect email or password.") for both "no such user" and
  "wrong password" — do not reveal which was wrong. Re-render `login.html` with HTTP 200.
- On success: set `session["user_id"] = row["id"]` and
  `redirect(url_for("profile"))`. Do not store the password or hash in the session.
- `logout` must call `session.clear()` (or pop `user_id`), flash a confirmation, and
  `redirect(url_for("landing"))`; it must not error when already logged out.
- Close the DB connection in all code paths.
- `session` relies on `app.secret_key`, which is already configured — do not hardcode a
  new secret.

## Definition of done
A specific, testable checklist — each item verifiable by running the app:
- [ ] `GET /login` still renders the form (200).
- [ ] `POST /login` with the seeded demo account (`demo@spendly.com` / `demo123`)
      redirects to `/profile` (302) and sets a session cookie.
- [ ] `POST /login` with a wrong password re-renders `login.html` with a visible generic
      error, HTTP 200, and sets no session.
- [ ] `POST /login` with an unknown email shows the same generic error (no user
      enumeration).
- [ ] `POST /login` with a blank email or blank password re-renders with an error.
- [ ] Email is matched case-insensitively (`DEMO@SPENDLY.COM` logs in).
- [ ] After logging in, `base.html` nav shows `Profile` and `Sign out` instead of
      `Sign in` / `Get started`.
- [ ] `GET /logout` clears the session, flashes a confirmation, and redirects to `/`
      (302 → 200); nav returns to the logged-out state.
- [ ] `GET /logout` while already logged out still redirects to `/` without error.
- [ ] No unhandled exception / 500 for any of the above.
- [ ] App starts without errors (`python app.py`).
