# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly — a Flask expense-tracker web app, built incrementally as a step-by-step learning project. Placeholder routes and comments in the code (`app.py`, `database/db.py`) mark work as "coming in Step N" / "students will implement" — treat these as the intended build order, not dead code to clean up.

## Commands

```bash
pip install -r requirements.txt   # flask, werkzeug, pytest, pytest-flask
python app.py                     # run dev server at http://localhost:5001 (debug=True)
pytest                            # run tests
pytest path/to/test_file.py::test_name   # run a single test
```

There is no build step, linter, or frontend bundler — templates and static assets are served directly by Flask.

## Architecture

- `app.py` — single Flask app with all routes. Currently implemented: `/`, `/register`, `/login`, `/terms`, `/privacy` (all render templates directly, no backend logic yet). Placeholder routes returning plain strings: `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` — these are intended to grow real logic (auth, DB-backed CRUD) in later steps.
- `database/db.py` — intended to hold `get_db()` (SQLite connection, row_factory + foreign keys), `init_db()` (`CREATE TABLE IF NOT EXISTS`), and `seed_db()` (sample data). Not yet implemented; SQLite is the target DB (`expense_tracker.db`, gitignored).
- `templates/base.html` — shared layout (nav, footer) that every page extends via `{% extends "base.html" %}`, with `head`/`content`/`scripts` blocks for page-specific CSS/JS.
- `static/css/style.css` — shared/base styles used across all pages.
- `static/css/landing.css` — page-specific styles, loaded only by `landing.html` via the `head` block. Follow this per-page CSS pattern (`static/css/<page>.css` + `{% block head %}`) rather than growing `style.css` unboundedly.
- `static/js/main.js` — loaded globally from `base.html`. Page-specific JS (e.g. `landing.js`) is loaded via the `scripts` block, same pattern as CSS.
- Currency/locale: amounts are formatted in ₹ (INR) — keep this consistent in new UI.

## Notes

- `.claude/worktrees/` contains git worktrees used for isolated in-progress work (e.g. a `merge-css` worktree) — not part of the app itself.
