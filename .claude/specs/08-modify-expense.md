# Spec: Modify Expense

## Overview
Spendly can now record expenses (Step 7) but once a row is written there is no
way to correct it — a wrong amount, category, date, or typo in the description is
permanent. This step delivers the update path: an "Edit expense" page,
pre-filled with an existing expense's current values, that revalidates the
submitted form with exactly the same rules as Add Expense and writes the changes
back with a parameterised `UPDATE` scoped to the current user. It reuses the
`EXPENSE_CATEGORIES` list, `_parse_iso_date`, and the validate-then-persist
pattern established in Step 7, and adds the ownership check (a user may only edit
their own expenses) that delete (Step 9) will also rely on.

## Depends on
- Step 1: Database setup (`users`, `expenses` tables, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 5: Profile page backend routes (recent-activity table)
- Step 6: Date filter for profile page (`_parse_iso_date`)
- Step 7: Add Expense (`EXPENSE_CATEGORIES`, validation rules, `add_expense.html`)

## Routes
- `GET /expenses` — list the current user's expenses, each linking to its edit
  form — logged-in only. Reached from a "Modify expense" link next to
  "+ Add expense" on the profile page.
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in only; only the owner may load it.
- `POST /expenses/<int:id>/edit` — validate the submitted form; on success
  `UPDATE` that expense row and redirect to `/profile` with a success flash; on
  failure re-render the form with an error message and the submitted values
  preserved — logged-in only; only the owner may submit.

The existing placeholder `@app.route("/expenses/<int:id>/edit")` (returns a plain
string, no methods) is replaced by this real `GET`/`POST` implementation. No
other new routes.

## Database changes
No database changes. The `expenses` table already has every column involved
(`id`, `user_id`, `amount`, `category`, `date`, `description`). Verified against
`database/db.py`.

## Templates
- **Create**: `templates/edit_expense.html` — extends `base.html`, loads
  `edit-expense.css` via the `head` block. Same field set as `add_expense.html`
  (amount, category `<select>`, date, optional description), a validation error
  banner, and a Cancel link back to `/profile`. The form `POST`s to
  `url_for('edit_expense', id=expense.id)`. All fields are pre-populated from the
  expense being edited (or from the rejected submission on a validation error).
- **Create**: `templates/expenses.html` — extends `base.html`, loads
  `expenses.css`. Lists every expense the user owns (date, description, category,
  amount) with a per-row "Edit" link to `url_for('edit_expense', id=e.id)`, an
  empty state, and a "Back to profile" link.
- **Modify**: `templates/profile.html` — add a "Modify expense" link next to the
  existing "+ Add expense" link in the "Recent transactions" card head, pointing
  to `url_for('list_expenses')`. No per-row controls, no logic changes.

## Files
- `app.py`
  - Replace the placeholder `edit_expense` view with a `GET`/`POST` handler
    decorated with `@login_required` and `methods=["GET", "POST"]`.
  - Load the target row with
    `SELECT id, amount, category, date, description FROM expenses
    WHERE id = ? AND user_id = ?` using `(id, session["user_id"])`. If no row is
    returned, `abort(404)` — this covers both "does not exist" and "belongs to
    another user" without leaking which.
  - `GET`: render `edit_expense.html` with the row's current values.
  - `POST`: reuse the Step 7 validation — `amount` parses as a finite `float`
    `> 0`; `category in EXPENSE_CATEGORIES`; `date` via `_parse_iso_date`;
    `description` stripped, capped at 200 chars, stored `NULL` when blank.
  - On success: parameterised
    `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
    WHERE id = ? AND user_id = ?`, then `conn.commit()`; flash
    `"Expense updated."` (category `success`) and redirect to
    `url_for('profile')`.
  - On validation failure: re-render `edit_expense.html` with an `error` and the
    submitted `amount` / `category` / `date` / `description`; respond `200`, do
    not redirect.
  - Add a `list_expenses` view (`GET /expenses`, `@login_required`) that selects
    `id, date, description, category, amount` for `session["user_id"]` ordered
    `date DESC, id DESC` and renders `expenses.html`.
- `templates/profile.html` — add the "Modify expense" link next to
  "+ Add expense".

## Files to create
- `templates/edit_expense.html` — the edit-expense form page.
- `static/css/edit-expense.css` — page-specific styles, loaded via the
  `{% block head %}` in `edit_expense.html`. CSS variables only. May be a thin
  file if it mostly reuses the shared `auth-*` / `form-*` classes that
  `add-expense.css` already styles.
- `templates/expenses.html` — the "Modify expense" list page.
- `static/css/expenses.css` — styles for the list page, loaded via its
  `{% block head %}`. CSS variables only.

## New dependencies
No new dependencies. Uses `abort` from Flask (already importable) and the
existing `get_db()`, `_parse_iso_date`, `EXPENSE_CATEGORIES`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only — every user-supplied value bound as a `?`
  parameter, never string-formatted into SQL. The `id` from the URL and the
  session `user_id` are both bound parameters.
- Passwords hashed with werkzeug (no auth changes in this step).
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.
- `@login_required` on both methods.
- Ownership is enforced in SQL on **every** access — the initial `SELECT`, and
  the `UPDATE` — with `AND user_id = ?` bound to `session["user_id"]`. A user
  must never be able to read or modify another user's expense; a mismatched or
  missing row is a `404`.
- The `id` used for the `UPDATE` comes from the URL route parameter only, never
  from a form field.
- All validation is server-side and identical to Step 7; HTML5 attributes are a
  convenience only.
- Amount stored as a `float`, `NaN`/`inf` and values `<= 0` rejected, rounded to
  2 decimal places.
- `date` stored as an ISO `YYYY-MM-DD` string (`.isoformat()`).
- Blank description stored as SQL `NULL`, not `""`.
- No inline styles in the template — all styling via `edit-expense.css` / shared
  classes.
- Keep amounts formatted with the `₹` symbol / `inr` filter wherever the page
  displays money.

## Definition of done
- [ ] `GET /expenses/<id>/edit` while logged out redirects to `/login`.
- [ ] `GET /expenses/<id>/edit` for an expense the logged-in user owns renders a
      form pre-filled with that expense's current amount, category, date, and
      description.
- [ ] The category `<select>` lists exactly the canonical categories and has the
      expense's current category pre-selected.
- [ ] `GET` / `POST /expenses/<id>/edit` for an id that does not exist returns
      `404`.
- [ ] `GET` / `POST /expenses/<id>/edit` for an expense owned by a *different*
      user returns `404` and does not disclose or modify it.
- [ ] Submitting valid changes (e.g. amount `99.99`, category `Transport`)
      updates that row, redirects to `/profile`, and shows a success flash.
- [ ] The edited values are immediately reflected in the profile's recent
      activity, total spent, transaction count, and category breakdown.
- [ ] Submitting a missing/non-numeric amount, amount `<= 0`, an out-of-list
      category, or an unparseable date re-renders the form with an error and does
      **not** change the row.
- [ ] On a validation error the previously entered (rejected) values are shown in
      the form, not the original DB values.
- [ ] Submitting a blank description stores `NULL` for `description`.
- [ ] A description longer than 200 characters is handled consistently with
      Step 7 (trimmed to 200).
- [ ] The profile page shows a "Modify expense" link next to "+ Add expense"
      that opens `GET /expenses`.
- [ ] `GET /expenses` while logged out redirects to `/login`; while logged in it
      lists the user's expenses, each with a working "Edit" link to that
      expense's edit form.
- [ ] `edit_expense.html` extends `base.html` and loads `edit-expense.css` via
      the `head` block; no new hex colour values are introduced.
- [ ] All monetary amounts on the page render with the `₹` symbol.
