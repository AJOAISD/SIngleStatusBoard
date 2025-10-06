from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3, os

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_SECURE_KEY"

DB_FILE = "data/buses.db"
os.makedirs("data", exist_ok=True)

USERNAME = "admin"
PASSWORD = "password123"

def init_db():
    first_time = not os.path.exists(DB_FILE)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if first_time:
            c.execute("""
                CREATE TABLE IF NOT EXISTS buses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bus_number TEXT NOT NULL,
                    driver TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                );
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    run_time TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    driver TEXT NOT NULL,
                    sub_driver TEXT DEFAULT '',
                    bus_number TEXT NOT NULL
                );
            """)
        # If DB already exists, ensure runs table has sub_driver column (migration)
        else:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
            if c.fetchone():
                cols = [row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()]
                if 'sub_driver' not in cols:
                    c.execute("ALTER TABLE runs ADD COLUMN sub_driver TEXT DEFAULT ''")
        conn.commit()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session["logged_in"] = False
    return redirect(url_for("index"))

@app.route("/")
def index():
    with get_db() as conn:
        buses = conn.execute("SELECT * FROM buses ORDER BY CAST(bus_number AS INTEGER)").fetchall()
    return render_template("index.html", buses=buses)

@app.route("/runs")
def runs():
    with get_db() as conn:
        # Include formatted date (MM/DD/YYYY) and formatted run_time (AM/PM) for display;
        # keep raw date/time for correct ordering
        runs_data = conn.execute("""
            SELECT id,
                   run_date AS run_date_raw,
                   strftime('%m/%d/%Y', run_date) AS run_date,
                   CASE strftime('%w', run_date)
                       WHEN '0' THEN 'Sunday'
                       WHEN '1' THEN 'Monday'
                       WHEN '2' THEN 'Tuesday'
                       WHEN '3' THEN 'Wednesday'
                       WHEN '4' THEN 'Thursday'
                       WHEN '5' THEN 'Friday'
                       WHEN '6' THEN 'Saturday'
                   END AS day_of_week,
                   run_time AS run_time_raw,
                   ltrim(strftime('%I:%M %p', run_time), '0') AS run_time,
                   group_name,
                   destination,
                   driver,
                   sub_driver,
                   bus_number
            FROM runs
            ORDER BY run_date_raw, time(run_time_raw)
        """).fetchall()
    return render_template("runs.html", runs=runs_data)

@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    with get_db() as conn:
        c = conn.cursor()

        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                c.execute("INSERT INTO buses (bus_number, driver, status, notes) VALUES (?, ?, ?, ?)",
                          (request.form["bus_number"], request.form["driver"], request.form["status"], request.form["notes"]))
            elif action == "delete":
                c.execute("DELETE FROM buses WHERE id=?", (request.form["bus_id"],))
            elif action == "add_run":
                c.execute("""INSERT INTO runs (run_date, run_time, group_name, destination, driver, sub_driver, bus_number)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                          (request.form["run_date"], request.form["run_time"], request.form["group_name"],
                           request.form["destination"], request.form["driver"], request.form.get("sub_driver", ""), request.form["bus_number"]))
            elif action == "delete_run":
                c.execute("DELETE FROM runs WHERE id=?", (request.form["run_id"],))
            conn.commit()
            return redirect(url_for("admin"))

        buses = conn.execute("SELECT * FROM buses ORDER BY CAST(bus_number AS INTEGER)").fetchall()
        # Include formatted date (MM/DD/YYYY) and formatted run_time (AM/PM) for display;
        # keep raw date/time for correct ordering
        runs_data = conn.execute("""
            SELECT id,
                   run_date AS run_date_raw,
                   strftime('%m/%d/%Y', run_date) AS run_date,
                   CASE strftime('%w', run_date)
                       WHEN '0' THEN 'Sunday'
                       WHEN '1' THEN 'Monday'
                       WHEN '2' THEN 'Tuesday'
                       WHEN '3' THEN 'Wednesday'
                       WHEN '4' THEN 'Thursday'
                       WHEN '5' THEN 'Friday'
                       WHEN '6' THEN 'Saturday'
                   END AS day_of_week,
                   run_time AS run_time_raw,
                   ltrim(strftime('%I:%M %p', run_time), '0') AS run_time,
                   group_name,
                   destination,
                   driver,
                   bus_number
            FROM runs
            ORDER BY run_date_raw, time(run_time_raw)
        """).fetchall()
    return render_template("admin.html", buses=buses, runs=runs_data)

# ---------- AJAX endpoint for inline updates ----------
@app.route("/update_bus_field", methods=["POST"])
@login_required
def update_bus_field():
    data = request.get_json()
    bus_id = data.get("bus_id")
    field = data.get("field")
    value = data.get("value")

    if field not in ["driver", "status", "notes"]:
        return jsonify({"success": False, "error": "Invalid field"})

    with get_db() as conn:
        conn.execute(f"UPDATE buses SET {field}=? WHERE id=?", (value, bus_id))
        conn.commit()
    return jsonify({"success": True})
