# app.py - Main Flask Application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
import os
import logging
from datetime import date, datetime
import bcrypt

from config import SECRET_KEY, FACE_DATA_DIR, MODEL_DIR
from db import execute_query, init_db
# face_engine imported lazily per-route (avoid crash on import if cv2 missing)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.context_processor
def inject_now():
    return {'now': datetime.now()}


# ============================================================
# Auth Decorator
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated



# ============================================================
# HEALTH CHECK (required by Railway)
# ============================================================
@app.route('/health')
def health():
    """Lightweight health check — no DB call so it always responds fast."""
    return {'status': 'ok', 'service': 'face-attendance'}, 200


# ============================================================
# AUTH ROUTES
# ============================================================
@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = execute_query(
            "SELECT * FROM admin_users WHERE username=%s AND is_active=1",
            (username,), fetchone=True
        )
        
        if user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            session['admin_id'] = user['admin_id']
            session['admin_name'] = user['full_name']
            session['admin_role'] = user['role']
            
            execute_query("UPDATE admin_users SET last_login=NOW() WHERE admin_id=%s",
                          (user['admin_id'],))
            flash(f"Welcome, {user['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# ============================================================
# DASHBOARD
# ============================================================
@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'total_students': execute_query(
            "SELECT COUNT(*) AS c FROM students WHERE is_active=1", fetchone=True)['c'],
        'registered_students': execute_query(
            "SELECT COUNT(*) AS c FROM students WHERE is_registered=1 AND is_active=1", fetchone=True)['c'],
        'today_attendance': execute_query(
            "SELECT COUNT(DISTINCT ar.student_id) AS c FROM attendance_records ar "
            "JOIN attendance_sessions s ON ar.session_id=s.session_id "
            "WHERE s.session_date=CURDATE()", fetchone=True)['c'],
        'active_sessions': execute_query(
            "SELECT COUNT(*) AS c FROM attendance_sessions WHERE session_date=CURDATE() AND status='active'",
            fetchone=True)['c'],
    }
    
    recent_attendance = execute_query(
        """SELECT s.roll_number, s.name, d.dept_code, sub.subject_name, 
           ar.status, ar.confidence_score, ar.marked_at
           FROM attendance_records ar
           JOIN attendance_sessions sess ON ar.session_id=sess.session_id
           JOIN students s ON ar.student_id=s.student_id
           JOIN departments d ON s.dept_id=d.dept_id
           JOIN subjects sub ON sess.subject_id=sub.subject_id
           ORDER BY ar.marked_at DESC LIMIT 10""",
        fetch=True
    ) or []
    
    return render_template('dashboard.html', stats=stats, recent_attendance=recent_attendance)


# ============================================================
# STUDENT MANAGEMENT
# ============================================================
@app.route('/students')
@login_required
def students():
    dept_filter = request.args.get('dept', '')
    sem_filter = request.args.get('sem', '')
    
    query = """SELECT s.*, d.dept_name, d.dept_code FROM students s 
               JOIN departments d ON s.dept_id=d.dept_id WHERE s.is_active=1"""
    params = []
    
    if dept_filter:
        query += " AND s.dept_id=%s"
        params.append(dept_filter)
    if sem_filter:
        query += " AND s.semester=%s"
        params.append(sem_filter)
    
    query += " ORDER BY s.roll_number"
    students_list = execute_query(query, params or None, fetch=True) or []
    departments = execute_query("SELECT * FROM departments", fetch=True) or []
    
    return render_template('students.html', students=students_list, departments=departments,
                           dept_filter=dept_filter, sem_filter=sem_filter)


@app.route('/students/register', methods=['GET', 'POST'])
@login_required
def register_student():
    departments = execute_query("SELECT * FROM departments", fetch=True) or []
    
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip().upper()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        dept_id = request.form.get('dept_id')
        semester = request.form.get('semester')
        batch_year = request.form.get('batch_year')
        
        if not all([roll_number, name, dept_id, semester, batch_year]):
            flash('Please fill all required fields.', 'danger')
            return render_template('register_student.html', departments=departments)
        
        # Check duplicate
        existing = execute_query(
            "SELECT student_id FROM students WHERE roll_number=%s", (roll_number,), fetchone=True)
        if existing:
            flash(f'Student with roll number {roll_number} already exists!', 'danger')
            return render_template('register_student.html', departments=departments)
        
        student_id = execute_query(
            """INSERT INTO students (roll_number, name, email, phone, dept_id, semester, batch_year)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (roll_number, name, email, phone, dept_id, semester, batch_year)
        )
        
        flash(f'Student {name} registered successfully! Student ID: {student_id}', 'success')
        return redirect(url_for('capture_samples', student_id=student_id))
    
    return render_template('register_student.html', departments=departments)


@app.route('/students/<int:student_id>/capture')
@login_required
def capture_samples(student_id):
    student = execute_query(
        "SELECT s.*, d.dept_name FROM students s JOIN departments d ON s.dept_id=d.dept_id WHERE s.student_id=%s",
        (student_id,), fetchone=True
    )
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    return render_template('capture_samples.html', student=student)


@app.route('/students/<int:student_id>/mark-registered', methods=['POST'])
@login_required
def mark_registered(student_id):
    face_dir = os.path.join(FACE_DATA_DIR, f'student_{student_id}')
    count = 0
    if os.path.exists(face_dir):
        count = len([f for f in os.listdir(face_dir) if f.endswith('.jpg')])
    if count > 0:
        execute_query(
            "UPDATE students SET photo_sample_count=%s, is_registered=1 WHERE student_id=%s",
            (count, student_id)
        )
        flash(f'✅ Student registered with {count} face samples.', 'success')
    else:
        flash('⚠️ No face samples found. Please run the capture command first.', 'warning')
    return redirect(url_for('students'))


@app.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    execute_query("UPDATE students SET is_active=0 WHERE student_id=%s", (student_id,))
    flash('Student removed successfully.', 'info')
    return redirect(url_for('students'))


# ============================================================
# MODEL TRAINING
# ============================================================
@app.route('/train', methods=['GET', 'POST'])
@login_required
def train():
    if request.method == 'POST':
        success, message, count = train_model()
        if success:
            flash(f'✅ {message}', 'success')
        else:
            flash(f'❌ {message}', 'danger')
        return redirect(url_for('train'))
    
    # Get training stats
    registered = execute_query(
        "SELECT COUNT(*) AS c FROM students WHERE is_registered=1 AND is_active=1", fetchone=True)['c']
    model_exists = os.path.exists(os.path.join(MODEL_DIR, 'face_model.yml'))
    model_mtime = None
    if model_exists:
        mtime = os.path.getmtime(os.path.join(MODEL_DIR, 'face_model.yml'))
        model_mtime = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('train.html', registered=registered,
                           model_exists=model_exists, model_mtime=model_mtime)


# ============================================================
# ATTENDANCE
# ============================================================
@app.route('/attendance')
@login_required
def attendance():
    sessions = execute_query(
        """SELECT ase.*, sub.subject_name, sub.subject_code, d.dept_name,
           COUNT(ar.record_id) AS present_count
           FROM attendance_sessions ase
           JOIN subjects sub ON ase.subject_id=sub.subject_id
           JOIN departments d ON ase.dept_id=d.dept_id
           LEFT JOIN attendance_records ar ON ar.session_id=ase.session_id
           GROUP BY ase.session_id
           ORDER BY ase.session_date DESC, ase.start_time DESC LIMIT 50""",
        fetch=True
    ) or []
    return render_template('attendance.html', sessions=sessions)


@app.route('/attendance/new-session', methods=['GET', 'POST'])
@login_required
def new_session():
    departments = execute_query("SELECT * FROM departments", fetch=True) or []
    subjects = execute_query("SELECT * FROM subjects ORDER BY dept_id, semester", fetch=True) or []
    
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        dept_id = request.form.get('dept_id')
        semester = request.form.get('semester')
        session_date = request.form.get('session_date', date.today().isoformat())
        start_time = request.form.get('start_time', datetime.now().strftime('%H:%M'))
        
        session_id = execute_query(
            """INSERT INTO attendance_sessions (subject_id, dept_id, semester, session_date, start_time, marked_by)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (subject_id, dept_id, semester, session_date, start_time, session['admin_name'])
        )
        
        flash('Session created! Start face recognition.', 'success')
        return redirect(url_for('take_attendance', session_id=session_id))
    
    return render_template('new_session.html', departments=departments, subjects=subjects,
                           today=date.today().isoformat(),
                           current_time=datetime.now().strftime('%H:%M'))


@app.route('/attendance/session/<int:session_id>/take')
@login_required
def take_attendance(session_id):
    sess_data = execute_query(
        """SELECT ase.*, sub.subject_name, d.dept_name, d.dept_code
           FROM attendance_sessions ase
           JOIN subjects sub ON ase.subject_id=sub.subject_id
           JOIN departments d ON ase.dept_id=d.dept_id
           WHERE ase.session_id=%s""",
        (session_id,), fetchone=True
    )
    if not sess_data:
        flash('Session not found.', 'danger')
        return redirect(url_for('attendance'))
    
    return render_template('take_attendance.html', sess=sess_data)


# start_recognition removed - camera runs via take_attendance.py terminal script


@app.route('/attendance/session/<int:session_id>/report')
@login_required
def session_report(session_id):
    sess_data = execute_query(
        """SELECT ase.*, sub.subject_name, sub.subject_code, d.dept_name
           FROM attendance_sessions ase
           JOIN subjects sub ON ase.subject_id=sub.subject_id
           JOIN departments d ON ase.dept_id=d.dept_id
           WHERE ase.session_id=%s""",
        (session_id,), fetchone=True
    )
    
    # Students present
    present = execute_query(
        """SELECT s.roll_number, s.name, ar.confidence_score, ar.marked_at
           FROM attendance_records ar
           JOIN students s ON ar.student_id=s.student_id
           WHERE ar.session_id=%s AND ar.status='present'
           ORDER BY s.roll_number""",
        (session_id,), fetch=True
    ) or []
    
    # Students absent
    absent = execute_query(
        """SELECT s.roll_number, s.name FROM students s
           WHERE s.dept_id=%s AND s.semester=%s AND s.is_active=1
           AND s.student_id NOT IN (
               SELECT student_id FROM attendance_records WHERE session_id=%s
           ) ORDER BY s.roll_number""",
        (sess_data['dept_id'], sess_data['semester'], session_id), fetch=True
    ) or []
    
    return render_template('session_report.html', sess=sess_data,
                           present=present, absent=absent)


@app.route('/attendance/summary')
@login_required
def attendance_summary():
    dept_id = request.args.get('dept_id', 1)
    semester = request.args.get('semester', 1)
    
    summary = execute_query(
        """SELECT s.roll_number, s.name, 
           COUNT(CASE WHEN ar.status='present' THEN 1 END) AS present_count,
           COUNT(DISTINCT ase.session_id) AS total_sessions,
           ROUND(COUNT(CASE WHEN ar.status='present' THEN 1 END) / 
                 NULLIF(COUNT(DISTINCT ase.session_id), 0) * 100, 1) AS percentage
           FROM students s
           LEFT JOIN attendance_records ar ON ar.student_id=s.student_id
           LEFT JOIN attendance_sessions ase ON ar.session_id=ase.session_id 
               AND ase.dept_id=%s AND ase.semester=%s
           WHERE s.dept_id=%s AND s.semester=%s AND s.is_active=1
           GROUP BY s.student_id ORDER BY s.roll_number""",
        (dept_id, semester, dept_id, semester), fetch=True
    ) or []
    
    departments = execute_query("SELECT * FROM departments", fetch=True) or []
    return render_template('attendance_summary.html', summary=summary,
                           departments=departments, dept_id=int(dept_id), semester=int(semester))


# ============================================================
# API ENDPOINTS
# ============================================================
@app.route('/api/subjects/<int:dept_id>/<int:semester>')
@login_required
def api_subjects(dept_id, semester):
    subjects = execute_query(
        "SELECT * FROM subjects WHERE dept_id=%s AND semester=%s",
        (dept_id, semester), fetch=True
    ) or []
    return jsonify(subjects)


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    logger.info("🚀 Starting Face Attendance System...")
    logger.info("📦 Initializing database...")
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)