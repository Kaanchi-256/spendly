# Spec: Delete Expense

## Overview
Spendly can record (Step 7) and correct (Step 8) expenses, but a row that was
added by mistake — a duplicate, a test entry, an expense that was refunded — can
never be removed. This step delivers the delete path: a "Delete" control on each
row of the existing `/expenses` list (and on the edit form) that issues a
`POST` to `/expenses/<id>/delete`, which runs a parameterised `DELETE` scoped to
the current user and redirects back to the profile with a success flash. It
reuses the ownership-in-SQL pattern and the `abort(404)` "don't disclose"
behaviour established in Step 8. Deletion is a `POST`-only, state-changing
action — never a bare link/`GET` — so it cannot be triggered by a crawler,
prefetch, or an `<img>`-style cross-site request.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 5: Profile page backend routes (recent activity, totals, category breakdown)
- Step 7: Add Expense (`EXPENSE_CATEGORIES`, flash pattern)
- Step 8: Modify Expense (`GET /expenses` list page, `templates/expenses.html`,
  `templates/edit_expense.html`, ownership check + `abort(404)`)

## Routes
- `POST /expenses/<int:id>/delete` — delete the given expense and redirect to
  `/profile` with a success flash — logged-in only; only the owner may delete.
  A row that does not exist, or belongs to another user, returns `404`.

The existing placeholder `@app.route("/expenses/<int:id>/delete")` (no methods,
returns a plain string, currently reachable by `GET`) is **replaced** by this
real `POST`-only implementation. Issuing a `GET` to the path after this step
returns `405 Method Not Allowed`.

No other new routes.

## Database changes
No database changes. The `DELETE` operates on the existing `expenses` table
(`id`, `user_id`). Verified against `database/db.py`. There is no soft-delete
column and none is added — the row is removed outright.

## Templates
- **Modify**: `templates/expenses.html` — add a "Delete" control to each expense
  row, next to the existing "Edit" link. It is a small inline
  `<form method="POST" action="{{ url_for('delete_expense', id=e.id) }}">` with a
  submit button (styled as a link/danger button via a class, no inline styles).
  Add a matching `<th>` for the new column. Keep the empty state and
  "Back to profile" link unchanged.
- **Modify**: `templates/edit_expense.html` — add a second
  `<form method="POST" action="{{ url_for('delete_expense', id=expense_id) }}">`
  with a "Delete expense" submit button, placed after the edit `<form>` (it must
  not be nested inside it). This lets a user delete the expense they are already
  editing.
- **Modify**: `templates/profile.html` — no change required (the recent-activity
  table still has no per-row controls; deletion is reached via
  "Modify expense" → `/expenses`). Only touch it if a "Modify expense" link is
  somehow missing.

No new templates.

## Files
- `app.py`
  - Replace the placeholder `delete_expense` view with a `POST`-only handler
    decorated with `@login_required` and `methods=["POST"]`.
  - Run a single parameterised statement:
    `DELETE FROM expenses WHERE id = ? AND user_id = ?` with
    `(id, session["user_id"])`, then `conn.commit()`.
  - If `cursor.rowcount == 0` (no such row, or not owned by this user),
    `abort(404)` — covering both cases without disclosing which.
  - On success: `flash("Expense deleted.", "success")` and
    `redirect(url_for("profile"))`.
  - `id` comes from the URL route parameter only, never from a form field.
  - Close the connection in a `finally`.
- `templates/expenses.html` — add the per-row delete form + column header, and a
  `{% block scripts %}` loading `js/expenses.js`.
- `templates/edit_expense.html` — add the delete form after the edit form, and a
  `{% block scripts %}` loading `js/expenses.js`.

## Files to create
- `static/js/expenses.js` — a small client-side guard: on submit of a
  `.expenses-delete-form` / `.edit-delete-form`, show a native `window.confirm()`
  and `preventDefault()` if the user cancels. Loaded per-page via the `scripts`
  block (same pattern as `landing.js`). This is a convenience only — the route is
  still `POST`-only and there is no server-rendered confirmation page.

`static/css/expenses.css` and `static/css/edit-expense.css` **already exist**
(Step 8) and are edited, not created: a `.expenses-delete-btn` rule (link-style,
`color: var(--danger)`) and a `.btn-delete` rule (danger-outline button). The
`--danger` / `--danger-light` CSS variables already exist in
`static/css/style.css` `:root` — no new token is added.

## New dependencies
No new dependencies. Uses `abort` from Flask (already imported) and the existing
`get_db()`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only — the URL `id` and the session `user_id` are both
  bound as `?` parameters; never string-formatted into SQL.
- Passwords hashed with werkzeug (no auth changes in this step).
- Use CSS variables — never hardcode hex values. Reuse the existing `--danger` /
  `--danger-light` tokens for the delete affordance.
- All templates extend `base.html` (the modified templates already do).
- `@login_required` on the route.
- The route accepts `POST` only (`methods=["POST"]`). No `GET`, no confirmation
  page rendered by the server.
- Ownership is enforced in SQL: `DELETE ... WHERE id = ? AND user_id = ?` bound
  to `session["user_id"]`. A user must never be able to delete another user's
  expense; a mismatched or missing row is a `404` (via `rowcount == 0`).
- Deletion is permanent — the row is removed, not flagged. No cascade concerns
  (`expenses` has no child tables).
- The delete control in the templates is a `POST` form with a button, never an
  `<a href>`.
- No inline styles in the templates — the delete button is styled via a class in
  the existing per-page CSS.
- Keep any amounts shown on these pages formatted with the `₹` / `inr` filter
  (unchanged from Step 8).

## Definition of done
- [ ] `POST /expenses/<id>/delete` while logged out redirects to `/login` and
      does not delete the row.
- [ ] `GET /expenses/<id>/delete` returns `405` (route is `POST`-only).
- [ ] `POST /expenses/<id>/delete` for an expense the logged-in user owns removes
      that row from the database, redirects to `/profile`, and shows an
      "Expense deleted." success flash.
- [ ] After deleting, the expense no longer appears in the profile's recent
      activity, and the total spent, transaction count, and category breakdown
      all update to exclude it.
- [ ] After deleting, the expense no longer appears on `GET /expenses`.
- [ ] `POST /expenses/<id>/delete` for an id that does not exist returns `404`.
- [ ] `POST /expenses/<id>/delete` for an expense owned by a *different* user
      returns `404` and the row is still present in the database afterwards.
- [ ] The `/expenses` list page shows a "Delete" control on each row, as a
      `POST` form (not a link), next to the "Edit" link.
- [ ] The edit-expense page shows a "Delete expense" button that deletes the
      expense being edited and lands on `/profile` with the success flash.
- [ ] Deleting the last remaining expense leaves `/expenses` showing its empty
      state ("No expenses logged yet.") and `/profile` showing the "₹0.00" /
      empty-state values.
- [ ] No new hardcoded hex colour values are introduced — the delete affordance
      uses the existing `--danger` / `--danger-light` CSS variables.
- [ ] Submitting a delete triggers a `window.confirm()`; cancelling it leaves the
      expense untouched.
- [ ] The modified templates still extend `base.html` and load their existing
      per-page CSS.
