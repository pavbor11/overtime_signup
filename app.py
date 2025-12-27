from flask import Flask, render_template, request, jsonify, g
import sqlite3
from datetime import datetime, timedelta, date
import os
import csv

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'overtime.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'employeeList.csv')

app = Flask(__name__)

# --- DB helpers ---
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            work_date TEXT NOT NULL,
            shift TEXT NOT NULL DEFAULT 'day',
            created_at TEXT NOT NULL
        )
    ''')
    db.commit()

# --- CSV LOOKUP ---
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

# --- Utilities ---
def week_dates_for_week_start(sunday_date):
    return [(sunday_date + timedelta(days=i)).isoformat() for i in range(7)]

# --- Routes ---
@app.route('/')
def index():
    init_db()
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
    db = get_db()
    cur = db.cursor()

    # --- POST: dodawanie wpisu ---
    if request.method == 'POST':
        data = request.get_json()
        login = data.get('login')
        work_date = data.get('work_date')
        shift = data.get('shift') or 'day'
        if not login or not work_date:
            return jsonify({'error': 'login and work_date required'}), 400

        cur.execute(
            'INSERT INTO entries (login, work_date, shift, created_at) VALUES (?, ?, ?, ?)',
            (login, work_date, shift, datetime.utcnow().isoformat())
        )
        db.commit()
        return jsonify({'status': 'ok'})

    # --- GET ---
    week_start = request.args.get('week_start')
    day = request.args.get('day')
    month = request.args.get('month')

    # --- Miesiąc ---
    if month:
        try:
            month = int(month)
            if month < 1 or month > 12:
                raise ValueError()
        except ValueError:
            return jsonify({'error':'month must be 1-12'}), 400

        cur.execute("""
            SELECT login, work_date, shift FROM entries
            WHERE strftime('%m', work_date) = ?
            ORDER BY work_date ASC
        """, (f"{month:02}",))
        rows = cur.fetchall()

        entries = []
        for r in rows:
            emp = employee_lookup.get(r['login'], {})
            entries.append({
                'login': r['login'],
                'name': emp.get('name',''),
                'work_date': r['work_date'],
                'shift': r['shift']
            })
        return jsonify({'entries': entries})

    # --- Dzień ---
    if day:
        cur.execute("""
            SELECT login, shift FROM entries
            WHERE work_date = ?
            ORDER BY created_at ASC
        """, (day,))
        rows = cur.fetchall()

        day_shift, night_shift = [], []

        for r in rows:
            emp = employee_lookup.get(r['login'], {})
            entry = {
                'login': r['login'],
                'name': emp.get('name', ''),
                'shift_pattern': emp.get('shift', '')
            }
            if r['shift'] == 'night':
                night_shift.append(entry)
            else:
                day_shift.append(entry)

        return jsonify({
            'work_date': day,
            'day_shift': day_shift,
            'night_shift': night_shift
        })

    # --- Tydzień ---
    if not week_start:
        return jsonify({'error': 'week_start required'}), 400

    ws = datetime.fromisoformat(week_start).date()
    dates = week_dates_for_week_start(ws)

    placeholders = ','.join('?' for _ in dates)
    cur.execute(f"""
        SELECT login, work_date, shift FROM entries
        WHERE work_date IN ({placeholders})
        ORDER BY created_at ASC
    """, dates)
    rows = cur.fetchall()

    per_day = {d: {'day_shift': [], 'night_shift': []} for d in dates}
    for r in rows:
        if r['shift'] == 'night':
            per_day[r['work_date']]['night_shift'].append(r['login'])
        else:
            per_day[r['work_date']]['day_shift'].append(r['login'])

    return jsonify({'week_start': week_start, 'per_day': per_day})

# --- DELETE ENTRY ---
@app.route('/api/entries/delete', methods=['POST'])
def api_delete_entry():
    data = request.get_json()
    login = data.get('login')
    work_date = data.get('work_date')
    shift = data.get('shift')
    if not login or not work_date or not shift:
        return jsonify({'error':'missing data'}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM entries WHERE login=? AND work_date=? AND shift=?', (login, work_date, shift))
    db.commit()
    return jsonify({'status':'ok'})

if __name__ == '__main__':
    app.run(debug=True)  # lokalnie





