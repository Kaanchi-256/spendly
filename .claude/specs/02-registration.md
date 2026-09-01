# Spec: Registration

## Overview
This feature makes the `/register` page functional. Currently `GET /register` renders `register.html` but the form `POST` has no handler. Step 2 adds the `POST /register` logic: validate the submitted name, email, and password; hash the password with werkzeug; insert a new row into the `users` table (created in Step 1); and handle the duplicate-email case gracefully. On success the user is shown success message and redirected to the login page. This is the first write-path feature in Spendly and the entry point to the auth flow that Steps 3–4 (login, logout, profile) build on.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`) must be
  complete. It is.

## Routes
- `GET /register` — render the registration form — public *(already exists, unchanged)*
- `POST /register` — validate input, create the user, redirect to `/login` on success;
  re-render `register.html` with an `error` message on failure — public *(new handler on
  the existing route)*

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE,
`password_hash`, `created_at`) already covers everything this feature needs. Verified
against `database/db.py`.

## Templates
- Create: none.
- Modify: none required. `templates/register.html` already renders an `{{ error }}` block,
  posts to `/register`, and submits `name` / `email` / `password` fields. Optionally
  repopulate `name` and `email` on validation failure via a `form` value passed from the
  view (nice-to-have, not required).

## Files
- `app.py` — change the `register` view to accept `GET` and `POST`; implement the `POST`
  branch (validation, hashing, insert, redirect / error render). Add the needed imports
  (`request`, `redirect`, `url_for`; `render_template` already imported) and
  `werkzeug.security.generate_password_hash`.

## Files to create
None.

## New dependencies
No new dependencies. `flask` and `werkzeug` are already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw `sqlite3`.
- Parameterised queries only — never string-format values into SQL.
- Passwords hashed with werkzeug (`generate_password_hash`); never store the raw password.
- Use CSS variables — never hardcode hex values (no CSS changes expected here).
- All templates extend `base.html` (no new templates expected here).
- Server-side validation is authoritative (do not rely on the HTML `required` attributes):
  - `name` — required, trimmed, non-empty (suggest max length 100).
  - `email` — required, trimmed, lowercased before storing, must contain a basic `@`/`.`
    shape.
  - `password` — required, minimum 8 characters (matches the template placeholder).
- Duplicate email: check with a parameterised `SELECT`, and/or catch
  `sqlite3.IntegrityError` from the UNIQUE constraint; re-render `register.html` with a
  user-facing `error` ("An account with that email already exists.") and HTTP 200. Never
  leak a stack trace.
- On any validation failure, re-render `register.html` with a single `error` string and do
  not create a user.
- On success, `redirect(url_for('login'))` — do not auto-login (sessions arrive in Step 3).
- Close the DB connection in all code paths.

## Definition of done
A specific, testable checklist — each item verifiable by running the app:
- [ ] `GET /register` still renders the form (200).
- [ ] Submitting valid new details creates exactly one `users` row and redirects to
      `/login` (302 → 200).
- [ ] The stored `password_hash` is not the plaintext password and
      `check_password_hash(hash, password)` returns `True`.
- [ ] The stored `email` is lowercased and trimmed.
- [ ] Submitting an email that already exists (e.g. `demo@spendly.com`) re-renders
      `register.html` with a visible error and creates no new row.
- [ ] Submitting a blank name, a malformed email, or a password shorter than 8 characters
      re-renders the form with an error and creates no new row.
- [ ] No unhandled exception / 500 for any of the above cases.
- [ ] App starts without errors (`python app.py`).
