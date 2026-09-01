# Spec: Login and Logout

## Overview
This feature makes the auth flow usable end to end. Registration (Step 2) creates users but there is currently no way to authenticate as one: `GET /login` renders `login.html`, the form `POST` has no handler, and `/logout` is a placeholder string. Step 3 adds `POST /login` (look up the user by email, verify the password hash with werkzeug, and store `user_id` / `user_name` in the Flask session on success) and a working `GET /logout` that clears the session. It also teaches `base.html` to show "Sign out" instead of "Sign in / Get started" when a session is active. This is the foundation every logged-in feature from Step 4 onward (profile, expense CRUD) builds on.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`). Complete.
- Step 2 — Registration (`POST /register` creating rows with a werkzeug password hash). Complete.

## Routes
- `GET /login` — render the login form — public *(already exists, unchanged)*
- `POST /login` — validate input, verify credentials, set the session, redirect to `/` on success; re-render `login.html` with an `error` on failure — public *(new handler on the existing route)*
- `GET /logout` — clear the session and redirect to `/login` with a flash message — public *(replaces the placeholder string)*

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`) covers everything. Verified against `database/db.py`.

## Templates
- Create: none.
- Modify:
  - `templates/base.html` — in `.nav-links`, show a "Sign out" link (`url_for('logout')`) and the user's name when `session.get('user_id')` is set; otherwise show the existing "Sign in" / "Get started" links.
  - `templates/login.html` — no structural change required; it already renders `{{ error }}`, posts to `/login`, and submits `email` / `password`. Optionally repopulate `email` on failure via a passed value (nice-to-have, not required).

## Files
- `app.py` — implement the `login` view for `GET` and `POST` (lookup, `check_password_hash`, `session` assignment, redirect / error render); replace the `logout` placeholder with `session.clear()` + redirect. Add imports: `session` from `flask`, `check_password_hash` from `werkzeug.security`.
- `templates/base.html` — conditional nav links (see Templates).

## Files to create
None.

## New dependencies
No new dependencies. `flask` and `werkzeug` are already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw `sqlite3`.
- Parameterised queries only — never string-format values into SQL.
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare plaintext.
- Use CSS variables — never hardcode hex values (no new CSS expected; reuse existing `auth-*` classes).
- All templates extend `base.html`.
- Server-side validation is authoritative:
  - `email` — required, trimmed, lowercased before lookup.
  - `password` — required, non-empty.
- On missing fields or no matching user or a bad password, re-render `login.html` with a single generic `error` ("Invalid email or password.") and HTTP 200 — do not reveal which field was wrong, and do not set the session.
- On success, store only `user_id` and `user_name` in `session`, then `redirect(url_for('landing'))` (the dashboard target moves to the Step 4 route once it exists).
- `logout` calls `session.clear()`, flashes a message, and redirects to `url_for('login')`. It must not error when no one is logged in.
- Close the DB connection in all code paths.
- Do not add `@login_required` protection to other routes in this step — that arrives with the first logged-in page in Step 4.

## Definition of done
A specific, testable checklist — each item verifiable by running the app:
- [ ] `GET /login` still renders the form (200).
- [ ] Submitting the demo credentials (`demo@spendly.com` / `demo123`) redirects to `/` (302 → 200) and the nav shows "Sign out".
- [ ] After login, `session` contains `user_id` and `user_name` and not the password.
- [ ] Submitting a wrong password for an existing email re-renders `login.html` with the generic error and sets no session.
- [ ] Submitting an email with no account shows the same generic error (no user enumeration).
- [ ] Submitting a blank email or blank password re-renders the form with an error, no 500.
- [ ] Email is matched case-insensitively (`DEMO@SPENDLY.COM` works).
- [ ] `GET /logout` clears the session, redirects to `/login`, shows a flash message, and the nav shows "Sign in" again.
- [ ] `GET /logout` while not logged in still redirects to `/login` without error.
- [ ] App starts without errors (`python app.py`).
