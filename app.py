#userlogin
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

#logger
import os
import csv
from datetime import datetime, date

#analytics


app = Flask(__name__)
app.secret_key = 'mysecrekey'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True



def init_db():
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password TEXT NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            muscle_group TEXT NOT NULL,
            equipment TEXT,
            instruction TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            weight REAL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        try:
            conn = sqlite3.connect('workout_tracker.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Registration succesful. Please log in.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username already taken", "error")
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('workout_tracker.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user'] = user[1]
            session['user_id'] = user[0]
            return redirect('/dashboard')
        else:
            flash("Invalid credentials", "error")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    #Summary card
    username = session['user']
    user_id = session['user_id']
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    c.execute('''SELECT COUNT(DISTINCT date), COALESCE (SUM(weight), 0), MAX(date)
              FROM workouts WHERE user_id = ?''', (user_id,))
    summary = c.fetchone()

    c.execute('''SELECT DISTINCT date FROM workouts 
              WHERE user_id = ? ORDER BY date DESC LIMIT 5''', (user_id,))
    recent_dates = [row[0] for row in c.fetchall()]

    recent_workouts = {}
    for date in recent_dates:
        c.execute('''SELECT e.name, w.set_number, w.reps, w.weight 
                  FROM workouts w
                  JOIN exercises e ON w.exercise_id = e.id
                  WHERE w.user_id = ? AND w.date = ?
                  ORDER BY e.name, w.set_number''', (user_id, date))
        recent_workouts[date] = c.fetchall()

    conn.close()

    return render_template('dashboard.html', username=username, recent_workouts=recent_workouts, summary=summary)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


@app.route('/log_workout', methods=['GET', 'POST'])
def log_workout():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        data = request.get_json()
        user_id = session['user_id']
        date = data.get('date', datetime.now().strftime("%Y-%m-%d"))
        entries = data.get('entries', [])

        conn = sqlite3.connect('workout_tracker.db')
        c = conn.cursor()
        try:
            for entry in entries:
                exercise_id = entry['exercise_id']
                for idx, s in enumerate(entry['sets']):
                    c.execute('''INSERT INTO workouts (user_id, date, exercise_id, set_number, reps, weight, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (user_id, date, exercise_id, idx + 1, s['reps'], s['weight'], s.get('notes','')))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            print("Error loggin workout:", e)
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute("SELECT name, muscle_group FROM exercises")
    exercises = c.fetchall()
    conn.close()

    return render_template('log_workout.html', exercise=exercises, current_date=datetime.now().strftime("%Y-%m-%d"))


@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')
    
    user_id = session['user_id']

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    c.execute('''SELECT DISTINCT date FROM workouts
              WHERE user_id = ? ORDER BY date DESC''', (user_id,))
    dates = [row[0] for row  in c.fetchall()]

    all_workouts = {}
    for date in dates:
        c.execute('''SELECT e.name, w.set_number, w.reps, w.weight
                  FROM workouts w
                  JOIN exercises e ON w.exercise_id = e.id
                  WHERE w.user_id = ? AND w.date = ?
                  ORDER BY e.name, w.set_number''', (user_id, date))
        all_workouts[date] = c.fetchall()

    conn.close()

    return render_template('history.html', all_workouts=all_workouts, dates=dates)


@app.route('/analytics', methods=['GET', 'POST'])
def analytics():
    if 'user' not in session:
        return redirect('/login')
    
    user_id = session['user_id']

    if request.method == "POST":
        exercise_filter = request.form.get('exercise','')
        start_date = request.form.get('start-date', '2025-01-01')
        end_date = request.form.get('end-date', datetime.now().strftime("%Y-%m-%d"))
    else:
        exercise_filter = request.args.get('exercise','')
        start_date = request.args.get('start-date', '2025-01-01')
        end_date = request.args.get('end-date', datetime.now().strftime("%Y-%m-%d"))

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    #sets per workout
    c.execute('''
        SELECT date, COUNT(*) as freq
        FROM workouts
        WHERE user_id = ?
        GROUP BY date
        ORDER BY date
        ''', (user_id,))
    freq_data = c.fetchall()

    #progression_chart
    progression = []
    if exercise_filter:
        c.execute('''
            SELECT w.date, MAX(w.weight)
            FROM workouts w
            JOIN exercises e ON w.exercise_id = e.id
            WHERE w.user_id = ? AND e.name = ? AND w.date BETWEEN ? AND ?
            GROUP BY w.date
            ORDER BY w.date
            ''', (user_id, exercise_filter, start_date, end_date))
    progression = c.fetchall()

    c.execute('''
        SELECT DISTINCT name FROM exercises ORDER BY name
        ''')
    exercises = c.fetchall()

    if not exercise_filter and exercises:
        exercise_filter = exercises[0][0]

    

    sets_dates = [row[0] for row in freq_data]
    sets_counts = [row[1] for row in freq_data]

    prog_dates = [row[0] for row in progression]
    prog_weights = [row[1] for row in progression]

    c.execute('''
        SELECT COUNT(DISTINCT date), SUM(reps * weight)
        FROM workouts
        WHERE user_id = ?
        ''', (user_id,))
    result = c.fetchone()
    total_days = result[0] or 0
    total_weight = round(result[1] or 0, 2)

    conn.close()    

    return render_template('analytics.html',total_days=total_days, total_weight=total_weight, exercises=exercises, sets_dates=sets_dates, sets_counts=sets_counts, prog_dates=prog_dates, prog_weights=prog_weights, selected_exercise=exercise_filter, start_date=start_date, end_date=end_date) 
                           

@app.route("/recommend_routine", methods=["GET", "POST"])
def recommend_routine():
    if request.method == "POST":
        level = request.form.get("level")
        days = int(request.form.get("days"))

        session['selected_level'] = level
        session['selected_days'] = days

        return redirect("/routine_results")

    return render_template("recommend_routine.html")


@app.route("/routine_results")
def routine_results():
    level = session.get('selected_level')
    days = session.get('selected_days')

    if not level or not days:
        flash("Please select your routine preferences.")
        return redirect("/recommend_routine")

    conn = sqlite3.connect('workout_tracker.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM workout_routines WHERE level = ? AND days_per_week = ?", (level, days))
    routines = cur.fetchall()
    conn.close()

    return render_template("routine_results.html", routines=routines)


@app.route('/routine/<int:routine_id>')
def view_routine(routine_id):
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    c.execute("SELECT name FROM workout_routines WHERE id = ?", (routine_id,))
    routine = c.fetchone()
    if not routine:
        return "Routine not found", 404

    # Get exercises grouped by day
    c.execute("""
        SELECT rd.day_name, e.name, rd.sets, rd.reps
        FROM routine_days rd
        JOIN exercises e ON rd.exercise_id = e.id
        WHERE rd.routine_id = ?
        ORDER BY rd.day_name, rd.id
    """, (routine_id,))
    rows = c.fetchall()
    conn.close()

    routine_days = {}
    for day_name, ex_name, sets, reps in rows:
        routine_days.setdefault(day_name, []).append((ex_name, sets, reps))

    return render_template('view_routine.html', routine_name=routine[0], routine_days=routine_days)



if __name__ == '__main__':
    init_db()
    app.run(debug=True)

    