#userlogin
from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

#logger
import os
import csv
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'mysecrekey'


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
            target_muscle_group TEXT NOT NULL,
            equipment TEXT,
            instruction TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT NOT NULL,
            exercise TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            weight REAL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
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


    """ summary card """
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    c.execute('''SELECT date, exercise, set_number, reps, weight FROM workouts
                ORDER BY date DESC LIMIT 5''')
    recent_workouts = c.fetchall()

    c.execute('''SELECT COUNT(*), SUM(weight), MAX(date) FROM workouts''')
    summary = c.fetchone()

    conn.close()

    return render_template('dashboard.html', username=session['user'], recent_workouts=recent_workouts, summary=summary)

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
                exercise = entry['exercise']
                for idx, s in enumerate(entry['sets']):
                    c.execute('''INSERT INTO workouts (user_id, date, exercise, set_number, reps, weight, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (user_id, date, exercise, idx + 1, s['reps'], s['weight'], s.get('notes','')))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            print("Error loggin workout:", e)
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute("SELECT name, target_muscle_group FROM exercises")
    exercises = c.fetchall()
    conn.close()

    return render_template('log_workout.html', exercise=exercises, current_date=datetime.now().strftime("%Y-%m-%d"))

    

if __name__ == '__main__':
    init_db()
    app.run(debug=True)