Project snapshot
- Minimal Flask app serving a status board for school buses (single-file app: `app.py`).
- SQLite DB stored at `data/buses.db` (created automatically by the app). Templates live in `templates/`.

High-level architecture (why/how)
- app.py: single-process Flask app. Routes render Jinja templates from `templates/` and operate directly on SQLite via the builtin `sqlite3` module.
- Frontend is server-rendered HTML + a tiny bit of inline JS (in `templates/admin.html`) that auto-saves edits via AJAX to two endpoints (`/update_bus_field`, `/update_run_field`).
- QR generation endpoint `/run_qr/<id>` creates a PNG pointing to Google Maps for a run's destination (uses `qrcode` and `Pillow`).

Key files to inspect
- `app.py` — core logic: DB init/migration, CRUD handlers, AJAX endpoints, authentication constants.
- `templates/admin.html` — where inline-edit inputs/selects are defined (look for `data-field` attributes and `data-bus-id` / `data-run-id` on rows).
- `templates/index.html` and `templates/runs.html` — public display pages; `index.html` uses CSS classes to map `status` strings to colors.
- `requirements.txt` — declared deps: `flask`, `gunicorn`, `qrcode`, `Pillow`.

Important conventions & data contracts (do not break)
- DB path: `DB_FILE = "data/buses.db"`. The app creates `data/` at startup. Never change DB location without updating `init_db()` and deployment.
- `buses` table columns: id, bus_number, driver, status, notes. Code assumes `bus_number` can be cast to integer for ordering: SQL uses `ORDER BY CAST(bus_number AS INTEGER)`.
- `runs` table columns: id, run_date (YYYY-MM-DD), run_time (HH:MM), group_name, destination, driver, sub_driver, bus_number. `run_date` and `run_time` are stored as text but SQL queries assume ISO date/time formats for ordering/strftime.
- Migration: on first run the app creates both tables; if `runs` exists but lacks `sub_driver`, `init_db()` adds it via `ALTER TABLE` — keep migrations lightweight and compatible.

AJAX / inline-edit contract
- Client JS in `templates/admin.html` sends JSON to these endpoints:
  - POST /update_bus_field  { bus_id, field, value }
  - POST /update_run_field  { run_id, field, value }
- Allowed fields (server-side whitelist):
  - buses: driver, status, notes
  - runs: run_date, run_time, group_name, destination, driver, sub_driver, bus_number
- Date/time validation: `run_date` expected YYYY-MM-DD (from `<input type="date">`), `run_time` expected HH:MM (from `<input type="time">`). Keep UI inputs consistent with these types.
- Column name interpolation: server uses parameterized values but interpolates the column name into SQL (e.g., `UPDATE buses SET {field}=?`). Only update fields present in the whitelist to avoid SQL injection.

Auth & secrets
- Credentials are hardcoded in `app.py`: `USERNAME`, `PASSWORD`, and `app.secret_key` set to a placeholder. For any real deployment change these immediately (or refactor to read from environment variables).

Run / dev workflows (reproducible)
1) Create a venv and install deps:
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
2) Run locally with Flask dev server (quick):
   export FLASK_APP=app.py
   export FLASK_ENV=development
   flask run --host=0.0.0.0 --port=5000
3) Run with gunicorn for production-like behavior (requirements include `gunicorn`):
   gunicorn "app:app" -w 4 -b 0.0.0.0:8000

Developer patterns to follow
- When adding new inline-editable fields, update both `templates/admin.html` (add `data-field` attribute on the input/select) and the corresponding server-side whitelist in `app.py`.
- Prefer parameterized SQL for values; if you must inject an identifier (column/table), validate it against a whitelist first.
- Keep UI inputs using appropriate input types (`date`, `time`) so the server-side validation stays simple.

Common fixes & gotchas
- If `sub_driver` is missing after a deploy, the app's migration should add it automatically; check `PRAGMA table_info(runs)` if DB was created differently.
- The app creates `data/` automatically; to inspect DB use `sqlite3 data/buses.db`.
- To change the admin credentials or secret key, update `app.py` or wire env var usage; remember to restart the server.

If you need more detail
- Ask for specific tasks (e.g., "add API for exporting runs as CSV", "switch to environment-based secrets", "add unit tests around DB init"). I can update code and tests directly.
