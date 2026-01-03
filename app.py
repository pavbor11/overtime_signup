from __future__ import annotations

import os
import csv
from datetime import datetime, timedelta, date

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract, UniqueConstraint, func
from sqlalchemy.exc import IntegrityError


BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "data", "employeeList.csv")

app = Flask(__name__)


# ----------------------------
# Database configuration (Render-only Postgres)
# ----------------------------
def normalize_database_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError(
        "DATABASE_URL is not set. This app is configured to run only with Render Postgres."
    )

app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(db_url)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)


# ----------------------------
# Models
# ----------------------------
class Entry(db.Model):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("login", "work_date", name="uq_entries_login_work_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(255), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    shift = db.Column(db.String(20), nullable=False, default="day")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# ----------------------------
# CSV LOOKUP
# ----------------------------
def load_employee_lookup() -> dict[str, dict[str, str]]:
    lookup_dict: dict[str, dict[str, str]] = {}
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            login = (row.get("User ID", "") or "").strip().lower()
            if not login:
                continue
            lookup_dict[login] = {
                "name": (row.get("Employee Name", "") or "").strip(),
                "shift": (row.get("Shift Pattern", "") or "").strip(),
                "manager": (row.get("Menago", "") or "").strip(),
            }
    return lookup_dict


try:
    employee_lookup = load_employee_lookup()
except Exception as e:
    print("Employee CSV load error:", e)
    employee_lookup = {}


# ----------------------------
# Utilities
# ----------------------------
def week_dates_for_week_start(sunday_date: date):
    return [sunday_date + timedelta(days=i) for i in range(7)]


def norm_manager(s: str | None) -> str:
    # trim + collapse spaces + lower
    return " ".join((s or "").strip().split()).lower()


# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/weeks")
def api_weeks():
    today = date.today()
    # python weekday(): Mon=0..Sun=6
    days_to_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
    current_sunday = today - timedelta(days=days_to_sunday)

    weeks = []
    for i in range(-3, 4):
        s = current_sunday + timedelta(weeks=i)
        weeks.append({
            "label": s.strftime("%U") + " / " + s.strftime("%Y"),
            "start": s.isoformat(),
            "pretty": s.strftime("%d/%m/%Y")
        })
    return jsonify(weeks)


@app.route("/api/entries", methods=["GET", "POST"])
def api_entries():
    # --- POST: dodawanie wpisu ---
    if request.method == "POST":
        data = request.get_json() or {}
        login = (data.get("login") or "").strip().lower()
        work_date_str = data.get("work_date")
        shift = (data.get("shift") or "day").strip().lower()

        if not login or not work_date_str:
            return jsonify({"error": "login and work_date required"}), 400

        if login not in employee_lookup:
            return jsonify({"error": "Niepoprawny login."}), 422

        try:
            wd = datetime.fromisoformat(work_date_str).date()
        except ValueError:
            return jsonify({"error": "work_date must be ISO format YYYY-MM-DD"}), 400

        e = Entry(login=login, work_date=wd, shift=shift, created_at=datetime.utcnow())
        db.session.add(e)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "Duplikat: ten login jest już dodany dla tej daty."}), 409

        return jsonify({"status": "ok"})

    # --- GET ---
    week_start = request.args.get("week_start")
    day = request.args.get("day")
    month = request.args.get("month")

    # --- Miesiąc ---
    if month:
        try:
            month_int = int(month)
            if month_int < 1 or month_int > 12:
                raise ValueError()
        except ValueError:
            return jsonify({"error": "month must be 1-12"}), 400

        rows = (
            db.session.query(Entry)
            .filter(extract("month", Entry.work_date) == month_int)
            .order_by(Entry.work_date.asc(), Entry.created_at.asc())
            .all()
        )

        entries = []
        for r in rows:
            emp = employee_lookup.get(r.login, {})
            entries.append({
                "login": r.login,
                "name": emp.get("name", ""),
                "work_date": r.work_date.isoformat(),
                "shift": r.shift
            })
        return jsonify({"entries": entries})

    # --- Dzień ---
    if day:
        try:
            day_date = datetime.fromisoformat(day).date()
        except ValueError:
            return jsonify({"error": "day must be ISO format YYYY-MM-DD"}), 400

        rows = (
            db.session.query(Entry)
            .filter(Entry.work_date == day_date)
            .order_by(Entry.created_at.asc())
            .all()
        )

        day_shift, night_shift = [], []
        for r in rows:
            emp = employee_lookup.get(r.login, {})
            entry = {
                "login": r.login,
                "name": emp.get("name", ""),
                "shift_pattern": emp.get("shift", "")
            }
            if r.shift == "night":
                night_shift.append(entry)
            else:
                day_shift.append(entry)

        return jsonify({
            "work_date": day,
            "day_shift": day_shift,
            "night_shift": night_shift
        })

    # --- Tydzień ---
    if not week_start:
        return jsonify({"error": "week_start required"}), 400

    try:
        ws = datetime.fromisoformat(week_start).date()
    except ValueError:
        return jsonify({"error": "week_start must be ISO format YYYY-MM-DD"}), 400

    dates = week_dates_for_week_start(ws)

    rows = (
        db.session.query(Entry)
        .filter(Entry.work_date.in_(dates))
        .order_by(Entry.created_at.asc())
        .all()
    )

    per_day = {d.isoformat(): {"day_shift": [], "night_shift": []} for d in dates}
    for r in rows:
        key = r.work_date.isoformat()
        if r.shift == "night":
            per_day[key]["night_shift"].append(r.login)
        else:
            per_day[key]["day_shift"].append(r.login)

    return jsonify({"week_start": week_start, "per_day": per_day})


@app.route("/api/entries/delete", methods=["POST"])
def api_delete_entry():
    data = request.get_json() or {}
    login = (data.get("login") or "").strip().lower()
    work_date = data.get("work_date")
    shift = (data.get("shift") or "").strip().lower()

    if not login or not work_date or not shift:
        return jsonify({"error": "missing data"}), 400

    try:
        wd = datetime.fromisoformat(work_date).date()
    except ValueError:
        return jsonify({"error": "work_date must be ISO format YYYY-MM-DD"}), 400

    db.session.query(Entry).filter(
        Entry.login == login,
        Entry.work_date == wd,
        Entry.shift == shift
    ).delete(synchronize_session=False)
    db.session.commit()

    return jsonify({"status": "ok"})


# ----------------------------
# Quarter summary endpoint
# ----------------------------
@app.route("/api/summary/quarter")
def api_summary_quarter():
    q = request.args.get("q")
    year = request.args.get("year")

    try:
        q_int = int(q)
        if q_int < 1 or q_int > 4:
            raise ValueError()
    except Exception:
        return jsonify({"error": "q must be 1-4"}), 400

    try:
        year_int = int(year) if year else date.today().year
    except Exception:
        return jsonify({"error": "year must be an integer"}), 400

    quarter_months = {
        1: [1, 2, 3],
        2: [4, 5, 6],
        3: [7, 8, 9],
        4: [10, 11, 12],
    }[q_int]

    # 6 tabel które pokazujesz na froncie
    MANAGERS = ["Paweł", "Michał", "Mariia", "Aleksy", "Piotr", "Daria"]
    OTHER_BUCKET = "Inni"

    per_manager = {m: [] for m in MANAGERS}
    per_manager[OTHER_BUCKET] = []

    # Mapowanie "jak w CSV" -> "jak ma być w tabelach"
    # (CSV ma imiona bez polskich znaków: Pawel, Michal)
    manager_aliases = {
        "pawel": "Paweł",
        "michal": "Michał",
        "mariia": "Mariia",
        "daria": "Daria",
        "piotr": "Piotr",
        "aleksy": "Aleksy",
    }

    def resolve_manager(mgr_raw: str | None) -> str:
        key = norm_manager(mgr_raw)
        return manager_aliases.get(key, OTHER_BUCKET)

    rows = (
        db.session.query(Entry.login, func.count(Entry.id).label("cnt"))
        .filter(extract("year", Entry.work_date) == year_int)
        .filter(extract("month", Entry.work_date).in_(quarter_months))
        .group_by(Entry.login)
        .all()
    )

    for login, cnt in rows:
        login_l = (login or "").strip().lower()
        emp = employee_lookup.get(login_l, {})
        mgr = resolve_manager(emp.get("manager", ""))

        per_manager[mgr].append({
            "login": login_l,
            "count": int(cnt),
        })

    # sortowanie i top 5
    for m in per_manager:
        per_manager[m].sort(key=lambda x: (-x["count"], x["login"]))
        per_manager[m] = per_manager[m][:5]

    return jsonify({
        "quarter": q_int,
        "year": year_int,
        "months": quarter_months,
        "per_manager": per_manager
    })


# Create tables if they do not exist (simple setup; ok for small app)
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
