# Spec: Date Filter For Profile Page

## Overview
The `/profile` page currently shows a user's spending summary, category
breakdown, and recent activity computed over *all* of their expenses. This
step adds a date-range filter so a logged-in user can narrow every section of
the page to a chosen period (e.g. "this month", "last 30 days", or a custom
start/end date). It is the first piece of interactive querying in Spendly and
sets the pattern — reading validated query-string params and threading a date
window through the profile queries — that later reporting features will reuse.

## Depends on
- Step 1: Database setup (`users`, `expenses` tables, `get_db()`)
- Step 2: Registration
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4: Profile page static UI
- Step 5: Profile page backend routes (live DB queries in `profile()`)

## Routes
- `GET /profile` — **modified**, not new. Now also reads optional
  `start`, `end`, and `range` query-string parameters and filters all three
  data sections (summary stats, category breakdown, recent activity) to that
  date window — logged-in only.

No new routes.

## Database changes
No database changes. `expenses.date` is stored as an ISO `YYYY-MM-DD` string,
which sorts and compares correctly with `>=` / `<=` in SQLite.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter form above the "Spending summary" card: a `GET` form to
    `/profile` with two `<input type="date">` fields (`start`, `end`) and
    quick-range links/buttons for "This month", "Last 30 days", and "All time".
  - Show the currently active range as a caption (e.g. "Showing 1 Sep – 3 Sep 2026").
  - When the filtered result set is empty, the existing empty-states must show
    (no crash, no stale totals).
  - Pre-fill the date inputs with the active `start` / `end` values.

## Templates to create
No new templates.

## Files
- `app.py` — `profile()` view: parse and validate `start` / `end` / `range`,
  compute the effective date window, pass date bounds into the expense queries,
  and pass the active range back to the template. Add a small helper to resolve
  a named range (`this-month`, `last-30-days`, `all`) to concrete dates.
- `templates/profile.html` — add the filter form and active-range caption.
- `static/css/profile.css` — styles for the filter form and range controls
  (using existing CSS variables only).

## Files to create
No new files.

## New dependencies
No new dependencies. Use `datetime` / `date` from the standard library
(already imported in `app.py`).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — the date bounds must be passed as SQL
  parameters, never string-formatted into the query
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles in the template (the existing `cat-fill` width is the only
  pre-existing exception; do not add new ones)
- Validate `start` and `end` with `datetime.strptime(value, "%Y-%m-%d")`;
  on any parse failure ignore that bound rather than erroring
- If `start` > `end`, swap them so the range is always valid
- If no params are given, default to **all time** (unfiltered) so existing
  behaviour and Step 5 tests are unchanged
- `range` (named preset) takes precedence over `start`/`end` when both appear
- The three query sections (summary totals, category breakdown, recent
  activity) must all honour the same window; `top_category`, percentages, and
  counts are recomputed from the filtered rows
- An empty filtered result must render zeros / empty states, not raise

## Definition of done
- [ ] Visiting `/profile` with no query params shows the same totals as before
      this step (all-time)
- [ ] `/profile?start=2026-09-01&end=2026-09-10` restricts the summary total,
      transaction count, category breakdown, and recent activity table to
      expenses dated 1–10 Sep 2026 inclusive
- [ ] The date inputs are pre-filled with the active `start` / `end` after
      submitting the filter
- [ ] Clicking "This month" sets the range to the first day of the current
      month through today and updates every section
- [ ] Clicking "All time" clears the filter and restores unfiltered totals
- [ ] `/profile?start=not-a-date` does not error — it is treated as no start bound
- [ ] `/profile?start=2026-09-20&end=2026-09-01` is treated as 1 Sep – 20 Sep
      (bounds swapped)
- [ ] A range that matches no expenses shows the "No expenses logged yet" /
      "No activity yet" empty states with ₹0.00 total and 0 transactions
- [ ] All amounts still display with the ₹ symbol
- [ ] No hex colour values are added to `profile.css` — only CSS variables
