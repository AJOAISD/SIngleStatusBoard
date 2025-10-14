from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, abort
import sqlite3, os, io, urllib.parse
import qrcode
from PIL import Image

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
                    return_time TEXT DEFAULT '',
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
                if 'return_time' not in cols:
                    c.execute("ALTER TABLE runs ADD COLUMN return_time TEXT DEFAULT ''")
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
                c.execute("""INSERT INTO runs (run_date, run_time, return_time, group_name, destination, driver, sub_driver, bus_number)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                          (request.form["run_date"], request.form["run_time"], request.form.get("return_time", ""), request.form["group_name"],
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
                   sub_driver,
                   bus_number
            FROM runs
            ORDER BY run_date_raw, time(run_time_raw)
        """).fetchall()
    return render_template("admin.html", buses=buses, runs=runs_data)


@app.route('/run_qr/<int:run_id>')
def run_qr(run_id):
    # Generate a QR code that opens Google Maps search for the run's destination
    with get_db() as conn:
        r = conn.execute('SELECT destination FROM runs WHERE id=?', (run_id,)).fetchone()
        if not r:
            return abort(404)
        destination = r['destination']

    # Build Google Maps search URL (encode the destination)
    params = urllib.parse.quote_plus(destination)
    maps_url = f'https://www.google.com/maps/search/?api=1&query={params}'

    # Generate QR code PNG
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(maps_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

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


@app.route("/update_run_field", methods=["POST"])
@login_required
def update_run_field():
    data = request.get_json()
    run_id = data.get("run_id")
    field = data.get("field")
    value = data.get("value")

    # Only allow specific fields to be updated inline
    allowed = {"run_date", "run_time", "return_time", "group_name", "destination", "driver", "sub_driver", "bus_number"}
    if field not in allowed:
        return jsonify({"success": False, "error": "Invalid field"})

    # Basic validation: ensure dates/times use expected formats for run_date/run_time
    if field == "run_date":
        # expecting YYYY-MM-DD from <input type=date>
        if not isinstance(value, str) or len(value.split("-")) != 3:
            return jsonify({"success": False, "error": "Invalid date format"})
    if field == "run_time":
        # expecting HH:MM from <input type=time>
        if not isinstance(value, str) or len(value.split(":")) < 2:
            return jsonify({"success": False, "error": "Invalid time format"})
    if field == "return_time":
        # expecting HH:MM from <input type=time>
        if not isinstance(value, str) or len(value.split(":")) < 2:
            return jsonify({"success": False, "error": "Invalid return time format"})

    with get_db() as conn:
        conn.execute(f"UPDATE runs SET {field}=? WHERE id=?", (value, run_id))
        conn.commit()
    return jsonify({"success": True})
