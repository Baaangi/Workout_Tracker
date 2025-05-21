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
        CREATE TABLE IF NOT EXISTS workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            exercise TEXT NOT NULL,
            sets INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            weight REAL,
            notes TEXT)''')
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

    c.execute('''SELECT date, exercise, sets, reps, weight FROM workouts
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
        date_val = request.form.get('date') or datetime.today().strftime('%Y-%m-%d')
        exercise = request.form['exercise']
        sets = request.form['sets']
        reps = request.form['reps']
        weight = request.form['weight']
        notes = request.form['notes']

        conn = sqlite3.connect('workout_tracker.db')
        c = conn.cursor()
        c.execute('''INSERT INTO workouts (date, exercise, sets, reps, weight, notes) VALUES (?, ?, ?, ?, ?, ?)''', 
                  (date_val, exercise, sets, reps, weight, notes))
        conn.commit()
        conn.close()
        flash('Workout logged succesfully', 'success')
        return redirect(url_for('log_workout'))
    
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute('SELECT name, target_muscle_group, equipment FROM exercises ORDER BY name')
    exercises = c.fetchall()
    conn.close()

    current_date = date.today().isoformat()

    return render_template('log_workout.html', exercise=exercises, current_date=current_date)
    

if __name__ == '__main__':
    init_db()
    app.run(debug=True)