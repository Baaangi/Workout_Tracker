#userlogin
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

#logger
import os
import csv
from datetime import datetime, date

#admin
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or not session.get('is_admin'):
            flash("Access Denied. Admins Only.", "error")
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated_function

#recommender
from recommender import build_similarity_matrix
DB_PATH = os.path.join(os.getcwd(), "workout_tracker.db")
similar_exercises = build_similarity_matrix(DB_PATH)


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
    
    # Safely alter table to add columns for user metrics (handles existing DB structures)
    columns_to_add = [
        ("age", "INTEGER"),
        ("gender", "TEXT"),
        ("weight", "REAL"),
        ("height", "REAL"),
        ("activity_level", "TEXT"),
        ("goal", "TEXT")
    ]
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            # Column already exists
            pass
    
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

    # Create daily_meals table for log diet records
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            food_name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

        # Create foods table for preloaded food options
    c.execute('''
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            serving_size REAL DEFAULT 100.0,
            serving_unit TEXT DEFAULT 'g',
            calories INTEGER NOT NULL,
            protein REAL DEFAULT 0.0,
            carbs REAL DEFAULT 0.0,
            fat REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB at import time so it runs under 'flask run'
init_db()



@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        # Read profile metric fields
        age = request.form.get('age')
        gender = request.form.get('gender')
        weight = request.form.get('weight')
        height = request.form.get('height')
        activity_level = request.form.get('activity_level')
        goal = request.form.get('goal')

        try:
            conn = sqlite3.connect('workout_tracker.db')
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (username, password, age, gender, weight, height, activity_level, goal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password, age, gender, weight, height, activity_level, goal))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username already taken", "error")
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods = ['GET', 'POST'])
def login():
    error = None
    
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
            session['is_admin'] = user[3]

            if user[3] == 1:
                return redirect('/admin')
            else:
                return redirect('/dashboard')
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)

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
                exercise_name = entry['exercise']
                c.execute("SELECT id FROM exercises WHERE name = ?", (exercise_name,))
                res = c.fetchone()
                if not res:
                    raise Exception(f"Exercise '{exercise_name}' not found.")
                exercise_id = res[0]

                for idx, s in enumerate(entry['sets']):
                    c.execute('''INSERT INTO workouts (user_id, date, exercise_id, set_number, reps, weight, notes)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (user_id, date, exercise_id, idx + 1, s['reps'], s['weight'], s.get('notes', '')))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            print("Error logging workout:", e)
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    # GET request
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute("SELECT name, muscle_group FROM exercises")
    exercises = c.fetchall()
    conn.close()

    # Handle prefilled exercises from recommended workout
    prefilled = []
    if 'recommended_workout' in session:
        ids = session.pop('recommended_workout')  # remove after using
        conn = sqlite3.connect('workout_tracker.db')
        c = conn.cursor()
        q_marks = ",".join("?" for _ in ids)
        c.execute(f"SELECT name FROM exercises WHERE id IN ({q_marks})", ids)
        prefilled = [row[0] for row in c.fetchall()]  # only pass exercise names to JS
        conn.close()

    return render_template(
        'log_workout.html',
        exercise=exercises,
        current_date=datetime.now().strftime("%Y-%m-%d"),
        prefilled=prefilled  # <-- this is crucial for JS prefill
    )



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
                           

@app.route("/workout_routine", methods=["GET", "POST"])
def workout_routine():
    if request.method == "POST":
        level = request.form.get("level")
        days = int(request.form.get("days"))

        session['selected_level'] = level
        session['selected_days'] = days

        return redirect("/routine_results")

    return render_template("workout_routine.html")


@app.route("/routine_results")
def routine_results():
    level = session.get('selected_level')
    days = session.get('selected_days')

    if not level or not days:
        flash("Please select your routine preferences.")
        return redirect("/workout_routine")

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
        SELECT rd.day_name, e.id, e.name, rd.sets, rd.reps
        FROM routine_days rd
        JOIN exercises e ON rd.exercise_id = e.id
        WHERE rd.routine_id = ?
        ORDER BY rd.day_name, rd.id
    """, (routine_id,))
    rows = c.fetchall()
    conn.close()

    routine_days = {}
    for day_name, ex_id, ex_name, sets, reps in rows:
        routine_days.setdefault(day_name, []).append((ex_id, ex_name, sets, reps))

    return render_template('view_routine.html', routine_name=routine[0], routine_days=routine_days)


@app.route("/recommender")
def recommender():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        select DISTINCT exercise_id from workouts
        WHERE user_id = ?
        ORDER BY date DESC LIMIT 3              
    """, (user_id,))
    recent = cursor.fetchall()
    recent_ids = [row[0] for row in recent]

    rec_ids = set()
    for eid in recent_ids:
        rec_ids.update(similar_exercises.get(eid, []))

    rec_ids = list(rec_ids - set(recent_ids))

    placeholders = ",".join("?" * len(rec_ids)) if rec_ids else "NULL"
    cursor.execute(f"""
        SELECT id, name, primary_muscle, equipment, type, difficulty FROM exercises
        WHERE id IN ({placeholders})               
    """, rec_ids)

    recommendations = cursor.fetchall()
    recommendations = recommendations[:5]
    conn.close()

    
    return render_template("recommender.html", recommendations=recommendations)


@app.route("/start_workout", methods=["POST"])
def start_workout():
    if 'user' not in session:
        return redirect('/login')

    exercise_ids = request.form.getlist("exercise_ids")

    # Store in session temporarily so /log_workout knows what to prefill
    session['recommended_workout'] = exercise_ids

    return redirect(url_for("log_workout"))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()

    if request.method == 'POST':
        age = request.form.get('age')
        gender = request.form.get('gender')
        weight = request.form.get('weight')
        height = request.form.get('height')
        activity_level = request.form.get('activity_level')
        goal = request.form.get('goal')

        c.execute("""
            UPDATE users
            SET age=?, gender=?, weight=?, height=?, activity_level=?, goal=?
            WHERE id=?
        """, (age, gender, weight, height, activity_level, goal, user_id))
        conn.commit()
        flash("Profile updated successfully!", "success")
        conn.close()
        return redirect('/profile')

    c.execute("SELECT age, gender, weight, height, activity_level, goal FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()

    profile_data = {
        'age': user_data[0] if user_data else None,
        'gender': user_data[1] if user_data else None,
        'weight': user_data[2] if user_data else None,
        'height': user_data[3] if user_data else None,
        'activity_level': user_data[4] if user_data else None,
        'goal': user_data[5] if user_data else None
    }

    return render_template('profile.html', profile=profile_data)


def calculate_targets(weight, height, age, gender, activity_level, goal):
    """
    Calculates Recommended Daily Calories and Macros based on Mifflin-St Jeor Equation
    """
    # Basal Metabolic Rate (BMR)
    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
    # Activity Level Multipliers
    multipliers = {
        'sedentary': 1.2,
        'lightly': 1.375,
        'moderately': 1.55,
        'very': 1.725,
        'extra': 1.9
    }
    multiplier = multipliers.get(activity_level, 1.2)
    
    # Total Daily Energy Expenditure (TDEE)
    tdee = bmr * multiplier
    
    # Adjust target based on goals
    if goal == 'lose':
        target_calories = int(tdee - 500)
    elif goal == 'gain':
        target_calories = int(tdee + 500)
    else: # maintain
        target_calories = int(tdee)
        
    # Macros calculations:
    # 1. Protein: 2.0 grams per kg of bodyweight (fit for training/muscle retention)
    protein_g = round(2.0 * weight, 1)
    protein_kcal = protein_g * 4
    
    # 2. Fat: 25% of target calories
    fat_kcal = target_calories * 0.25
    fat_g = round(fat_kcal / 9, 1)
    
    # 3. Carbs: Remaining calories
    carbs_kcal = max(0, target_calories - (protein_kcal + fat_kcal))
    carbs_g = round(carbs_kcal / 4, 1)
    
    return {
        'calories': max(1200, target_calories),  # Floor target at safe minimum of 1200
        'protein': protein_g,
        'carbs': carbs_g,
        'fat': fat_g
    }


@app.route('/diet')
def diet():
    if 'user' not in session:
        return redirect('/login')
        
    user_id = session['user_id']
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    
    # 1. Get user profile metrics
    c.execute("SELECT age, gender, weight, height, activity_level, goal FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    
    has_profile = False
    targets = None
    if user_data and all(x is not None for x in user_data):
        has_profile = True
        targets = calculate_targets(
            weight=user_data[2],
            height=user_data[3],
            age=user_data[0],
            gender=user_data[1],
            activity_level=user_data[4],
            goal=user_data[5]
        )
        
    # 2. Get logged meals for today
    c.execute("""
        SELECT id, food_name, calories, protein, carbs, fat 
        FROM daily_meals 
        WHERE user_id = ? AND date = ?
    """, (user_id, today_str))
    meals = c.fetchall()

    # 2b. Get preloaded foods from database
    c.execute("SELECT id, name, serving_size, serving_unit, calories, protein, carbs, fat FROM foods ORDER BY name")
    foods_rows = c.fetchall()
    conn.close()

    preloaded_foods = []
    for f in foods_rows:
        preloaded_foods.append({
            'id': f[0],
            'name': f[1],
            'serving_size': f[2],
            'serving_unit': f[3],
            'calories': f[4],
            'protein': f[5],
            'carbs': f[6],
            'fat': f[7]
        })
    
    # 3. Sum current daily intake
    intake = {
        'calories': sum(m[2] for m in meals),
        'protein': round(sum(m[3] for m in meals), 1),
        'carbs': round(sum(m[4] for m in meals), 1),
        'fat': round(sum(m[5] for m in meals), 1)
    }
    
    return render_template(
        'diet.html',
        has_profile=has_profile,
        targets=targets,
        meals=meals,
        intake=intake,
        current_date=today_str,
        preloaded_foods=preloaded_foods
    )



@app.route('/diet/add', methods=['POST'])
def add_meal():
    if 'user' not in session:
        return redirect('/login')
        
    user_id = session['user_id']
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    food_name = request.form.get('food_name')
    calories = request.form.get('calories')
    protein = request.form.get('protein', 0)
    carbs = request.form.get('carbs', 0)
    fat = request.form.get('fat', 0)
    
    # Provide fallbacks if macros left empty
    protein = float(protein) if protein else 0.0
    carbs = float(carbs) if carbs else 0.0
    fat = float(fat) if fat else 0.0
    
    if food_name and calories:
        conn = sqlite3.connect('workout_tracker.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO daily_meals (user_id, date, food_name, calories, protein, carbs, fat)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, today_str, food_name, int(calories), protein, carbs, fat))
        conn.commit()
        conn.close()
        flash("Meal logged successfully!", "success")
    else:
        flash("Food Name and Calories are required.", "danger")
        
    return redirect('/diet')


@app.route('/diet/add_preloaded', methods=['POST'])
def add_preloaded():
    if 'user' not in session:
        return redirect('/login')
        
    user_id = session['user_id']
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    food_id = request.form.get('food_id')
    quantity = request.form.get('quantity')
    
    if not food_id or not quantity:
        flash("Please select a food and enter a quantity.", "danger")
        return redirect('/diet')
        
    try:
        quantity = float(quantity)
    except ValueError:
        flash("Invalid quantity entered.", "danger")
        return redirect('/diet')
        
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    
    # Fetch preloaded food details
    c.execute("SELECT name, serving_size, serving_unit, calories, protein, carbs, fat FROM foods WHERE id = ?", (food_id,))
    food = c.fetchone()
    
    if not food:
        conn.close()
        flash("Food item not found.", "danger")
        return redirect('/diet')
        
    food_name, serving_size, serving_unit, calories, protein, carbs, fat = food
    
    # Scale calculations based on ratio of quantity to baseline serving_size
    ratio = quantity / serving_size
    scaled_calories = int(calories * ratio)
    scaled_protein = round(protein * ratio, 1)
    scaled_carbs = round(carbs * ratio, 1)
    scaled_fat = round(fat * ratio, 1)
    
    # Construct descriptive name: e.g. "Chicken Breast (150g)"
    if quantity.is_integer():
        logged_name = f"{food_name} ({int(quantity)}{serving_unit})"
    else:
        logged_name = f"{food_name} ({quantity:.1f}{serving_unit})"
        
    c.execute("""
        INSERT INTO daily_meals (user_id, date, food_name, calories, protein, carbs, fat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, today_str, logged_name, scaled_calories, scaled_protein, scaled_carbs, scaled_fat))
    
    conn.commit()
    conn.close()
    
    flash(f"Logged {logged_name} successfully!", "success")
    return redirect('/diet')



@app.route('/diet/delete/<int:meal_id>', methods=['POST'])
def delete_meal(meal_id):
    if 'user' not in session:
        return redirect('/login')
        
    user_id = session['user_id']
    
    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    # Ensure user owns the meal log
    c.execute("DELETE FROM daily_meals WHERE id = ? AND user_id = ?", (meal_id, user_id))
    conn.commit()
    conn.close()
    
    flash("Meal entry deleted.", "success")
    return redirect('/diet')


@app.route('/admin/foods', methods=['GET', 'POST'])
@admin_required
def admin_foods():
    if request.method == 'POST':
        name = request.form.get('name')
        serving_size = request.form.get('serving_size', 100.0)
        serving_unit = request.form.get('serving_unit', 'g')
        calories = request.form.get('calories')
        protein = request.form.get('protein', 0.0)
        carbs = request.form.get('carbs', 0.0)
        fat = request.form.get('fat', 0.0)

        # Sanitize and convert inputs
        serving_size = float(serving_size) if serving_size else 100.0
        calories = int(calories) if calories else 0
        protein = float(protein) if protein else 0.0
        carbs = float(carbs) if carbs else 0.0
        fat = float(fat) if fat else 0.0

        if not name or not calories:
            flash('Food Name and Calories are required', 'danger')
        else:
            conn = sqlite3.connect('workout_tracker.db')
            try:
                conn.execute("""
                    INSERT INTO foods (name, serving_size, serving_unit, calories, protein, carbs, fat)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, serving_size, serving_unit, calories, protein, carbs, fat))
                conn.commit()
                flash('Food item added successfully!', 'success')
            except sqlite3.IntegrityError:
                flash('Food item name must be unique', 'danger')
            finally:
                conn.close()

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute('SELECT * FROM foods ORDER BY name')
    foods = c.fetchall()
    conn.close()
    return render_template("admin/foods.html", foods=foods)


@app.route('/admin/delete_food/<int:food_id>', methods=['POST', 'GET'])
@admin_required
def delete_food(food_id):
    conn = sqlite3.connect('workout_tracker.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()
    flash("Food item deleted successfully!", "success")
    return redirect('/admin/foods')



#ADMIN_PAGES
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = sqlite3.connect("workout_tracker.db")

    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_exercises = conn.execute('SELECT COUNT(*) FROM exercises').fetchone()[0]
    total_workouts = conn.execute('SELECT COUNT(*) FROM workouts').fetchone()[0]
    total_admins = conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]

    recent_logs = conn.execute('''
        SELECT u.username, e.name AS exercise_name, w.date, w.reps, w.weight
        FROM workouts w
        JOIN users u ON w.user_id = u.id
        JOIN exercises e ON w.exercise_id = e.id
        ORDER BY w.date DESC
        LIMIT 5
    ''').fetchall()

    conn.close()
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_exercises=total_exercises,
                           total_workouts=total_workouts,
                           total_admins=total_admins,
                           recent_logs=recent_logs)


@app.route('/admin/users')
@admin_required
def admin_users():
    conn = sqlite3.connect("workout_tracker.db")
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin FROM users")
    users = c.fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    # prevent deleting your own account
    if user_id == session['user_id']:
        flash("You can't delete your own account.", "error")
        return redirect('/admin/users')

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully.", "success")
    return redirect('/admin/users')



@app.route('/admin/exercises', methods=['GET', 'POST'])
@admin_required
def admin_exercises():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    if request.method == 'POST':
        name = request.form.get('name')
        muscle_group = request.form.get('muscle_group')
        primary_muscle = request.form.get('primary_muscle')
        equipment = request.form.get('equipment')
        type = request.form.get('type') 
        difficulty = request.form.get("difficulty")

        if not all([name, muscle_group, primary_muscle, equipment, type, difficulty]):
                flash('All fields are required', 'danger')
        else:
            conn = sqlite3.connect('workout_tracker.db')
            try:
                conn.execute("""
                    INSERT INTO exercises (name, muscle_group, primary_muscle, equipment, type, difficulty)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, muscle_group, primary_muscle, equipment, type, difficulty))
                conn.commit()
                flash('Exercise added successfully!', 'success')
            except sqlite3.IntegrityError:
                flash('Exercise name must be unique', 'danger')
            conn.close()

    conn = sqlite3.connect('workout_tracker.db')
    c = conn.cursor()
    c.execute('SELECT * FROM exercises')
    exercises = c.fetchall()
    conn.close()
    return render_template("admin/exercises.html", exercises=exercises)


@app.route('/admin/delete_exercise/<int:exercise_id>', methods=['POST', 'GET'])
@admin_required
def delete_exercise(exercise_id):
    conn = sqlite3.connect('workout_tracker.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    conn.commit()
    conn.close()
    flash("Exercise deleted successfully!", "success")
    return redirect('/admin/exercises')

@app.route('/admin/edit_exercise/<int:exercise_id>', methods=['GET', 'POST'])
@admin_required
def edit_exercise(exercise_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')

    conn = sqlite3.connect('workout_tracker.db')
    if request.method == 'POST':
        name = request.form.get('name')
        muscle_group = request.form.get('muscle_group')
        primary_muscle = request.form.get('primary_muscle')
        equipment = request.form.get('equipment')
        type = request.form.get('type')
        difficulty = request.form.get('difficulty')

        if not all([name, muscle_group, primary_muscle, equipment, type, difficulty]):
            flash('All fields are required', 'danger')
        else:
            conn.execute("""
                UPDATE exercises
                SET name=?, muscle_group=?, primary_muscle=?, equipment=?, type=?, difficulty=?
                WHERE id=?
            """, (name, muscle_group, primary_muscle, equipment, type, difficulty, exercise_id))
            conn.commit()
            flash('Exercise updated successfully!', 'success')
            conn.close()
            return redirect('/admin/exercises')

    exercise = conn.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
    conn.close()
    return render_template('admin/edit_exercise.html', exercise=exercise)

    

@app.route('/admin/logs')
@admin_required
def admin_workout_logs():
    conn = sqlite3.connect('workout_tracker.db')
    logs = conn.execute('''
        SELECT w.id, u.username, e.name AS exercise_name, w.date, w.set_number, w.reps, w.weight, w.notes
        FROM workouts w
        JOIN users u ON w.user_id = u.id
        JOIN exercises e ON w.exercise_id = e.id
        ORDER BY w.date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/logs.html', logs=logs)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)

    