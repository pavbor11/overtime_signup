from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from datetime import datetime, timedelta, date
import os
import csv

# =========================
# Flask + SQLAlchemy setup
# =========================

app = Flask(__name__)

database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///overtime_local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# Models
# =========================

class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String, nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    shift = db.Column(db.String, nullable=False, default="day")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# =========================
# CSV LOOKUP
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'data', 'employeeList.csv')

def load_employee_lookup():
    lookup_dict = {}

    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')
        for row in reader:
            login = row['User ID'].strip().lower()
            lookup_dict[login] = {
                'name': row.get('Employee Name', ''),
                'shift': row.get('Shift Pattern', '')
            }

    return lookup_dict

employee_lookup = load_employee_lookup()

# =========================
# Utilities
# =========================

def week_dates_for_week_start(sunday_date):
    return [(sunday_date + timedelta(days=i)) for i in range(7)]

# =========================
# Routes
# =========================

@app.route('/')
def index():
    db.create_all()
    return render_template('index.html')

@app.route('/api/weeks')
def api_weeks():
    today = date.today()
    days_to_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
    current_sunday = today - timedelta(days=days_to_sunday)

    weeks = []
    for i in range(-3, 4):
        s = current_sunday + timedelta(weeks=i)
        weeks.append({
            'label': s.strftime('%U') + ' / ' + s.strftime('%Y'),
            'start': s.isoformat(),
            'pretty': s.strftime('%d/%m/%Y')
        })
    return jsonify(weeks)

@app.route('/api/entries', methods=['GET', 'POST'])
def api_entries():

    # -------- POST --------
    if request.method == 'POST':
        data = request.get_json()
        login = (data.get('login') or '').strip().lower()
        work_date_str = data.get('work_date')
        shift = data.get('shift') or 'day'

        if not login or not work_date_str:
            return jsonify({'error': 'login and work_date required'}), 400

        try:
            work_date = datetime.fromisoformat(work_date_str).date()
        except ValueError:
            return jsonify({'error': 'work_date must be YYYY-MM-DD'}), 400

        entry = Entry(
            login=login,
            work_date=work_date,
            shift=shift
        )
        db.session.add(entry)
        db.session.commit()

        return jsonify({'status': 'ok'})

    # -------- GET --------
    week_start = request.args.get('week_start')
    day = request.args.get('day')
    month = request.args.get('month')

    # -------- MONTH --------
    if month:
        try:
            month = int(month)
            if not 1 <= month <= 12:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'month must be 1-12'}), 400

        rows = (
            db.session.query(Entry)
            .filter(extract('month', Entry.work_date) == month)
            .order_by(Entry.work_date.asc())
            .all()
        )

        entries = []
        for r in rows:
            emp = employee_lookup.get(r.login, {})
            entries.append({
                'login': r.login,
                'name': emp.get('name', ''),
                'work_date': r.work_date.isoformat(),
                'shift': r.shift
            })

        return jsonify({'entries': entries})

    # -------- DAY --------
    if day:
        try:
            work_date = datetime.fromisoformat(day).date()
        except ValueError:
            return jsonify({'error': 'day must be YYYY-MM-DD'}), 400

        rows = (
            db.session.query(Entry)
            .filter(Entry.work_date == work_date)
            .order_by(Entry.created_at.asc())
            .all()
        )

        day_shift, night_shift = [], []

        for r in rows:
            emp = employee_lookup.get(r.login, {})
            entry = {
                'login': r.login,
                'name': emp.get('name', ''),
                'shift_pattern': emp.get('shift', '')
            }
            if r.shift == 'night':
                night_shift.append(entry)
            else:
                day_shift.append(entry)

        return jsonify({
            'work_date': work_date.isoformat(),
            'day_shift': day_shift,
            'night_shift': night_shift
        })

    # -------- WEEK --------
    if not week_start:
        return jsonify({'error': 'week_start required'}), 400

    ws = datetime.fromisoformat(week_start).date()
    dates = week_dates_for_week_start(ws)

    rows = (
        db.session.query(Entry)
        .filter(Entry.work_date.in_(dates))
        .order_by(Entry.created_at.asc())
        .all()
    )

    per_day = {d.isoformat(): {'day_shift': [], 'night_shift': []} for d in dates}

    for r in rows:
        if r.shift == 'night':
            per_day[r.work_date.isoformat()]['night_shift'].append(r.login)
        else:
            per_day[r.work_date.isoformat()]['day_shift'].append(r.login)

    return jsonify({'week_start': week_start, 'per_day': per_day})

# =========================
# DELETE ENTRY
# =========================

@app.route('/api/entries/delete', methods=['POST'])
def api_delete_entry():
    data = request.get_json()
    login = (data.get('login') or '').strip().lower()
    work_date_str = data.get('work_date')
    shift = data.get('shift')

    if not login or not work_date_str or not shift:
        return jsonify({'error': 'missing data'}), 400

    try:
        work_date = datetime.fromisoformat(work_date_str).date()
    except ValueError:
        return jsonify({'error': 'work_date must be YYYY-MM-DD'}), 400

    (
        db.session.query(Entry)
        .filter(
            Entry.login == login,
            Entry.work_date == work_date,
            Entry.shift == shift
        )
        .delete(synchronize_session=False)
    )
    db.session.commit()

    return jsonify({'status': 'ok'})

# =========================
# Local run
# =========================

if __name__ == '__main__':
    app.run(debug=True)
