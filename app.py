from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_SECURE_KEY"

DB_FILE = "data/buses.db"
os.makedirs("data", exist_ok=True)

USERNAME = "admin"
PASSWORD = "password123"

# ---------- Database Setup ----------
def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
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
                    bus_number TEXT NOT NULL
                );
            """)
            conn.commit()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

# ---------- Authentication ----------
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

# ---------- Routes ----------
@app.route("/")
def index():
    with get_db() as conn:
        buses = conn.execute("SELECT * FROM buses ORDER BY bus_number").fetchall()
    return render_template("index.html", buses=buses)

@app.route("/runs")
def runs():
    with get_db() as conn:
        runs_data = conn.execute("SELECT * FROM runs ORDER BY run_date, run_time").fetchall()
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
            elif action == "update":
                c.execute("UPDATE buses SET driver=?, status=?, notes=? WHERE id=?",
                          (request.form["driver"], request.form["status"], request.form["notes"], request.form["bus_id"]))
            elif action == "delete":
                c.execute("DELETE FROM buses WHERE id=?", (request.form["bus_id"],))
            elif action == "add_run":
                c.execute("""INSERT INTO runs (run_date, run_time, group_name, destination, driver, bus_number)
                             VALUES (?, ?, ?, ?, ?, ?)""",
                          (request.form["run_date"], request.form["run_time"], request.form["group_name"],
                           request.form["destination"], request.form["driver"], request.form["bus_number"]))
            elif action == "delete_run":
                c.execute("DELETE FROM runs WHERE id=?", (request.form["run_id"],))
            conn.commit()
            return redirect(url_for("admin"))

        buses = conn.execute("SELECT * FROM buses ORDER BY bus_number").fetchall()
        runs_data = conn.execute("SELECT * FROM runs ORDER BY run_date, run_time").fetchall()

    return render_template("admin.html", buses=buses, runs=runs_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
