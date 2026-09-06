# Spec: Add Expense

## Overview
Spendly can display a user's spending (profile summary, category breakdown,
recent activity) but there is still no way for a logged-in user to record a new
expense — the seed data is the only data that exists. This step delivers the
first write path into the `expenses` table: a dedicated "Add expense" page with
a validated form (amount, category, date, optional description) that inserts a
row scoped to the current user and returns them to their profile where the new
expense is immediately reflected in every section. It establishes the
form-handling, server-side validation, and ownership pattern that edit (Step 8)
and delete (Step 9) will build on.

## Depends on
- Step 1: Database setup (`users`, `expenses` tables, `get_db()`)
- Step 2: Registration
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4: Profile page static UI
- Step 5: Profile page backend routes (live DB queries in `profile()`)
- Step 6: Date filter for profile page (filtered profile queries)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only.
- `POST /expenses/add` — validate the submitted form; on success insert one
  `expenses` row for the current user and redirect to `/profile` with a success
  flash; on failure re-render the form with an error message and the submitted
  values preserved — logged-in only.

The existing placeholder `@app.route("/expenses/add")` (returns a plain string)
is replaced by this real implementation. No other new routes.

## Database changes
No database changes. The existing `expenses` table already has every column
needed: `user_id`, `amount REAL NOT NULL`, `category TEXT NOT NULL`,
`date TEXT NOT NULL` (ISO `YYYY-MM-DD`), `description TEXT` (nullable),
`created_at` (defaulted). Verified against `database/db.py`.

## Templates
- **Create**: `templates/add_expense.html` — extends `base.html`, renders the
  form (`POST` to `url_for('add_expense')`) with fields:
  - `amount` — `<input type="number" step="0.01" min="0.01">`, required
  - `category` — `<select>` populated from a canonical category list
  - `date` — `<input type="date">`, required, defaults to today
  - `description` — `<input type="text">` / `<textarea>`, optional, max 200 chars
  - An error banner shown when validation fails, and previously entered values
    re-populated.
- **Modify**: `templates/profile.html` — add a visible "Add expense" call to
  action (link/button to `url_for('add_expense')`) near the page heading or the
  recent-activity card so users can reach the new page. No logic changes.

## Files
- `app.py`
  - Replace the placeholder `add_expense` view with a `GET`/`POST` handler
    decorated with `@login_required`.
  - Add a module-level `EXPENSE_CATEGORIES` tuple (the canonical list:
    `Food`, `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`,
    `Other` — matching the seed data) used both to populate the `<select>` and
    to validate the submitted category.
  - Server-side validation: amount parses as a float, is `> 0`, and is finite;
    category is one of `EXPENSE_CATEGORIES`; date parses via
    `_parse_iso_date`; description is stripped and length-capped (≤ 200),
    stored as `NULL` when blank.
  - Parameterised `INSERT INTO expenses (user_id, amount, category, date,
    description) VALUES (?, ?, ?, ?, ?)` using `session["user_id"]`, then
    `conn.commit()`.
  - Flash `"Expense added."` (category `success`) and redirect to
    `url_for('profile')` on success.
- `templates/profile.html` — add the "Add expense" CTA (see Templates).

## Files to create
- `templates/add_expense.html` — the add-expense form page.
- `static/css/add-expense.css` — page-specific styles for the form, loaded via
  the `{% block head %}` in `add_expense.html` (per-page CSS pattern). CSS
  variables only.

## New dependencies
No new dependencies. Uses `datetime` / `date` from the standard library and the
existing `get_db()` helper.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only — every user-supplied value bound as a `?`
  parameter, never string-formatted into SQL.
- Passwords hashed with werkzeug (no auth changes in this step).
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.
- `@login_required` on both methods; the insert must use the session user id,
  never a user id from the form, so a user can only create their own expenses.
- All validation is server-side; HTML5 attributes (`required`, `min`, `step`)
  are a convenience only and must not be relied on.
- On any validation failure, re-render `add_expense.html` with an `error`
  message and the submitted `amount` / `category` / `date` / `description`
  so the user does not retype everything; respond `200`, do not redirect.
- Amount is stored as a `float`; reject `NaN`/`inf` and values `<= 0`.
- Round the stored amount to 2 decimal places.
- `date` is stored as an ISO `YYYY-MM-DD` string (`.isoformat()`), consistent
  with the seed data and the Step 6 date filter.
- Blank description is stored as SQL `NULL`, not `""`.
- No inline styles in the template — all styling via `add-expense.css`.
- Keep amounts formatted with the `₹` symbol / `inr` filter wherever the new
  page displays money.

## Definition of done
- [ ] `GET /expenses/add` while logged out redirects to `/login`.
- [ ] `GET /expenses/add` while logged in renders a form with amount, category,
      date, and description fields; the date field defaults to today.
- [ ] The category `<select>` lists exactly the canonical categories
      (`Food`, `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`,
      `Other`).
- [ ] Submitting a valid expense (e.g. amount `250.75`, category `Food`, today's
      date, description "Lunch") inserts one row in `expenses` with the correct
      `user_id`, redirects to `/profile`, and shows a success flash.
- [ ] The newly added expense immediately appears in the profile's recent
      activity, transaction count, total spent, and category breakdown
      (with no date filter applied).
- [ ] Submitting with a missing or non-numeric amount re-renders the form with
      an error and does **not** insert a row.
- [ ] Submitting amount `0` or a negative amount is rejected with an error.
- [ ] Submitting a category outside the canonical list is rejected with an
      error (not silently stored).
- [ ] Submitting an unparseable date is rejected with an error.
- [ ] Submitting with a blank description succeeds and stores `NULL` for
      `description`.
- [ ] A description longer than 200 characters is rejected (or trimmed per the
      implementation) — behaviour is consistent and covered.
- [ ] On a validation error the previously entered values are still shown in the
      form.
- [ ] One user cannot create an expense owned by another user (the insert uses
      the session user id only).
- [ ] `add_expense.html` extends `base.html` and loads `add-expense.css` via the
      `head` block; no new hex colour values are introduced.
- [ ] All monetary amounts on the new page render with the `₹` symbol.
