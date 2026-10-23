import os
import re
import secrets
import urllib.parse
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import check_password_hash
import database

app = Flask(__name__)
app.secret_key = "sunnyvale-primary-school-secure-session-key-2026"

# Hardened Session & Cookie Security Config
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

# Initialize and seed database
database.init_db()
database.seed_data_if_empty()

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = generate_csrf_token

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    return True, ""

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in with your credentials to access the school portal.", "info")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in as Administrator.", "info")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "Admin":
            flash("Access denied: Administrative privileges required.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def security_and_auth_check():
    # Ensure CSRF token is present in session
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)

    # CSRF verification for POST requests
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not token or token != session.get("_csrf_token"):
            flash("Security check failed: Invalid or expired CSRF security token.", "error")
            return redirect(request.referrer or url_for("dashboard"))

    # Route protection
    public_endpoints = ["login", "static", "report_card", "fee_receipt", "report_card_preview_data"]
    if request.endpoint and request.endpoint not in public_endpoints:
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))

@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

@app.context_processor
def inject_school_info():
    settings = database.get_school_settings()
    return {
        "school_name": settings.get("school_name", "SunnyVale Primary School"),
        "school_tagline": settings.get("school_tagline", "Nurturing Curious Minds & Bright Futures"),
        "academic_year": settings.get("academic_year", "2026 - 2027"),
        "current_term": settings.get("current_term", "Term 1 - Fall 2026"),
        "current_date": date.today().strftime("%A, %B %d, %Y"),
        "school_settings": settings
    }

# ----------------- AUTHENTICATION -----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "127.0.0.1"
        is_locked, remaining_mins = database.is_ip_locked(ip)
        if is_locked:
            flash(f"Security Alert: Account/IP is temporarily locked due to multiple failed attempts. Please retry in {remaining_mins} minute(s).", "error")
            return render_template("login.html")

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = database.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            database.record_login_success(ip, username)
            database.update_last_login(user["id"])

            csrf = session.get("_csrf_token")
            session.clear()
            if csrf:
                session["_csrf_token"] = csrf
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            session["email"] = user["email"]

            flash(f"Welcome back, {user['full_name']}! Signed in as {user['role']}.", "success")
            next_page = request.args.get("next")
            return redirect(next_page if next_page else url_for("dashboard"))
        else:
            count, is_locked_now = database.record_login_failure(ip, username)
            if is_locked_now:
                flash("Security Alert: 5 consecutive failed login attempts reached. Your access has been locked for 15 minutes.", "error")
            else:
                remaining = 5 - count
                flash(f"Invalid username or password. {remaining} attempt(s) remaining before temporary security lockout.", "error")

    # If already logged in, go straight to dashboard
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    username = session.get("username", "Unknown")
    database.add_security_log("LOGOUT", username, request.remote_addr or "127.0.0.1", f"User @{username} signed out safely.", "INFO")
    csrf = session.get("_csrf_token")
    session.clear()
    if csrf:
        session["_csrf_token"] = csrf
    flash("You have been signed out safely.", "info")
    return redirect(url_for("login"))

# ----------------- DASHBOARD -----------------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    today_str = date.today().strftime("%Y-%m-%d")
    with database.get_db() as conn:
        cursor = conn.cursor()

        # Counts
        cursor.execute("SELECT COUNT(*) as cnt FROM students WHERE status = 'Active'")
        total_students = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM teachers WHERE status = 'Active'")
        total_teachers = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM classes")
        total_classes = cursor.fetchone()["cnt"]

        # Today's attendance stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_recorded,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_count,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status = 'Excused' THEN 1 ELSE 0 END) as excused_count
            FROM attendance
            WHERE date = ?
        """, (today_str,))
        att_row = cursor.fetchone()
        
        # If no attendance taken today, fallback to latest recorded date
        if not att_row or att_row["total_recorded"] == 0:
            cursor.execute("""
                SELECT DISTINCT date FROM attendance ORDER BY date DESC LIMIT 1
            """)
            latest_date_row = cursor.fetchone()
            if latest_date_row:
                effective_date = latest_date_row["date"]
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_recorded,
                        SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
                        SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_count,
                        SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                        SUM(CASE WHEN status = 'Excused' THEN 1 ELSE 0 END) as excused_count
                    FROM attendance
                    WHERE date = ?
                """, (effective_date,))
                att_row = cursor.fetchone()
            else:
                effective_date = today_str
        else:
            effective_date = today_str

        tot = att_row["total_recorded"] if att_row and att_row["total_recorded"] else 0
        present = att_row["present_count"] if att_row and att_row["present_count"] else 0
        late = att_row["late_count"] if att_row and att_row["late_count"] else 0
        absent = att_row["absent_count"] if att_row and att_row["absent_count"] else 0
        excused = att_row["excused_count"] if att_row and att_row["excused_count"] else 0
        att_rate = round(((present + late) / tot * 100), 1) if tot > 0 else 0

        # Fees overview
        cursor.execute("""
            SELECT 
                COALESCE(SUM(amount), 0) as total_billed,
                COALESCE(SUM(paid_amount), 0) as total_collected,
                COALESCE(SUM(amount - paid_amount), 0) as total_outstanding
            FROM fees
        """)
        fee_stats = cursor.fetchone()

        # Class breakdown
        cursor.execute("""
            SELECT c.id, c.name, c.grade_level, COUNT(s.id) as student_count, c.capacity
            FROM classes c
            LEFT JOIN students s ON c.id = s.class_id AND s.status = 'Active'
            GROUP BY c.id
            ORDER BY c.id
        """)
        classes_data = cursor.fetchall()

        # Recent notices
        cursor.execute("SELECT * FROM notices ORDER BY date_posted DESC LIMIT 4")
        recent_notices = cursor.fetchall()

        # Recent student enrollments
        cursor.execute("""
            SELECT s.*, c.name as class_name 
            FROM students s
            JOIN classes c ON s.class_id = c.id
            ORDER BY s.id DESC LIMIT 5
        """)
        recent_students = cursor.fetchall()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_teachers=total_teachers,
        total_classes=total_classes,
        effective_date=effective_date,
        att_rate=att_rate,
        present=present,
        late=late,
        absent=absent,
        excused=excused,
        tot_attendance=tot,
        fee_stats=fee_stats,
        classes_data=classes_data,
        recent_notices=recent_notices,
        recent_students=recent_students
    )

# ----------------- STUDENTS -----------------
@app.route("/students")
def students():
    search = request.args.get("search", "").strip()
    class_filter = request.args.get("class_id", "")

    with database.get_db() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT s.*, c.name as class_name, c.grade_level
            FROM students s
            JOIN classes c ON s.class_id = c.id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.admission_no LIKE ? OR s.guardian_name LIKE ?)"
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard, wildcard])
        
        if class_filter:
            query += " AND s.class_id = ?"
            params.append(class_filter)
            
        query += " ORDER BY s.class_id ASC, s.last_name ASC"
        cursor.execute(query, params)
        students_list = cursor.fetchall()

        cursor.execute("SELECT * FROM classes ORDER BY id")
        classes_list = cursor.fetchall()

    return render_template(
        "students.html",
        students=students_list,
        classes=classes_list,
        search=search,
        selected_class=class_filter
    )

@app.route("/students/<int:student_id>")
def student_detail(student_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        
        # Student profile
        cursor.execute("""
            SELECT s.*, c.name as class_name, c.grade_level, t.full_name as homeroom_teacher
            FROM students s
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN teachers t ON c.teacher_id = t.id
            WHERE s.id = ?
        """, (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("students"))

        # Attendance stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_cnt,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_cnt,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_cnt,
                SUM(CASE WHEN status = 'Excused' THEN 1 ELSE 0 END) as excused_cnt
            FROM attendance
            WHERE student_id = ?
        """, (student_id,))
        att_summary = cursor.fetchone()

        cursor.execute("""
            SELECT date, status, remarks 
            FROM attendance 
            WHERE student_id = ? 
            ORDER BY date DESC LIMIT 10
        """, (student_id,))
        recent_attendance = cursor.fetchall()

        # Academic Grades
        cursor.execute("""
            SELECT g.*, sub.name as subject_name, sub.code as subject_code
            FROM grades g
            JOIN subjects sub ON g.subject_id = sub.id
            WHERE g.student_id = ?
            ORDER BY g.term DESC, sub.name ASC
        """, (student_id,))
        grades = cursor.fetchall()

        # Fee ledger
        cursor.execute("""
            SELECT * FROM fees 
            WHERE student_id = ? 
            ORDER BY due_date DESC
        """, (student_id,))
        student_fees = cursor.fetchall()

        # Classes for edit modal
        cursor.execute("SELECT * FROM classes ORDER BY id")
        all_classes = cursor.fetchall()

    return render_template(
        "student_detail.html",
        student=student,
        att_summary=att_summary,
        recent_attendance=recent_attendance,
        grades=grades,
        fees=student_fees,
        classes=all_classes
    )

@app.route("/students/new", methods=["POST"])
def add_student():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    dob = request.form.get("date_of_birth")
    gender = request.form.get("gender")
    class_id = request.form.get("class_id")
    guardian_name = request.form.get("guardian_name", "").strip()
    guardian_relation = request.form.get("guardian_relation", "Mother")
    guardian_phone = request.form.get("guardian_phone", "").strip()
    guardian_email = request.form.get("guardian_email", "").strip()
    home_address = request.form.get("home_address", "").strip()
    emergency_contact = request.form.get("emergency_contact", "").strip()
    medical_allergies = request.form.get("medical_allergies", "None").strip()

    with database.get_db() as conn:
        cursor = conn.cursor()
        # Generate admission number
        cursor.execute("SELECT MAX(id) as max_id FROM students")
        next_num = (cursor.fetchone()["max_id"] or 0) + 1
        admission_no = f"STU-2026-{next_num:03d}"

        avatar_colors = [
            "bg-blue-100 text-blue-700",
            "bg-emerald-100 text-emerald-700",
            "bg-purple-100 text-purple-700",
            "bg-amber-100 text-amber-700",
            "bg-rose-100 text-rose-700",
            "bg-cyan-100 text-cyan-700",
            "bg-indigo-100 text-indigo-700",
        ]
        avatar_color = avatar_colors[next_num % len(avatar_colors)]
        enrollment_date = date.today().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO students (
                admission_no, first_name, last_name, date_of_birth, gender,
                class_id, guardian_name, guardian_relation, guardian_phone,
                guardian_email, home_address, emergency_contact, medical_allergies,
                enrollment_date, status, avatar_color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
        """, (admission_no, first_name, last_name, dob, gender, class_id,
              guardian_name, guardian_relation, guardian_phone, guardian_email,
              home_address, emergency_contact, medical_allergies, enrollment_date, avatar_color))
        conn.commit()

    flash(f"Pupil {first_name} {last_name} enrolled successfully with ID {admission_no}!", "success")
    return redirect(url_for("students"))

@app.route("/students/<int:student_id>/edit", methods=["POST"])
def edit_student(student_id):
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    dob = request.form.get("date_of_birth")
    gender = request.form.get("gender")
    class_id = request.form.get("class_id")
    guardian_name = request.form.get("guardian_name", "").strip()
    guardian_relation = request.form.get("guardian_relation")
    guardian_phone = request.form.get("guardian_phone", "").strip()
    guardian_email = request.form.get("guardian_email", "").strip()
    home_address = request.form.get("home_address", "").strip()
    emergency_contact = request.form.get("emergency_contact", "").strip()
    medical_allergies = request.form.get("medical_allergies", "None").strip()
    status = request.form.get("status", "Active")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE students SET
                first_name = ?, last_name = ?, date_of_birth = ?, gender = ?,
                class_id = ?, guardian_name = ?, guardian_relation = ?,
                guardian_phone = ?, guardian_email = ?, home_address = ?,
                emergency_contact = ?, medical_allergies = ?, status = ?
            WHERE id = ?
        """, (first_name, last_name, dob, gender, class_id, guardian_name,
              guardian_relation, guardian_phone, guardian_email, home_address,
              emergency_contact, medical_allergies, status, student_id))
        conn.commit()

    flash("Student information updated successfully.", "success")
    return redirect(url_for("student_detail", student_id=student_id))

@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
    flash("Student record was deleted.", "info")
    return redirect(url_for("students"))

# ----------------- ATTENDANCE -----------------
@app.route("/attendance")
def attendance():
    selected_class_id = request.args.get("class_id")
    selected_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM classes ORDER BY id")
        classes = cursor.fetchall()

        if not selected_class_id and classes:
            selected_class_id = classes[0]["id"]
        elif selected_class_id:
            selected_class_id = int(selected_class_id)

        # Get students of selected class
        students_att = []
        if selected_class_id:
            cursor.execute("""
                SELECT s.id, s.admission_no, s.first_name, s.last_name, s.avatar_color,
                       a.status as att_status, a.remarks
                FROM students s
                LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
                WHERE s.class_id = ? AND s.status = 'Active'
                ORDER BY s.last_name ASC
            """, (selected_date, selected_class_id))
            students_att = cursor.fetchall()

        # Class details
        cursor.execute("SELECT * FROM classes WHERE id = ?", (selected_class_id,))
        active_class = cursor.fetchone()

    return render_template(
        "attendance.html",
        classes=classes,
        selected_class_id=selected_class_id,
        selected_date=selected_date,
        students=students_att,
        active_class=active_class
    )

@app.route("/attendance/save", methods=["POST"])
def save_attendance():
    class_id = request.form.get("class_id")
    att_date = request.form.get("date")

    with database.get_db() as conn:
        cursor = conn.cursor()
        # Find all student inputs
        for key, value in request.form.items():
            if key.startswith("status_"):
                student_id = int(key.replace("status_", ""))
                status = value
                remarks = request.form.get(f"remarks_{student_id}", "").strip()
                
                cursor.execute("""
                    INSERT INTO attendance (student_id, date, status, remarks)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(student_id, date) DO UPDATE SET
                        status = excluded.status,
                        remarks = excluded.remarks
                """, (student_id, att_date, status, remarks))
        conn.commit()

    flash(f"Daily attendance for {att_date} has been saved successfully!", "success")
    return redirect(url_for("attendance", class_id=class_id, date=att_date))

# ----------------- TEACHERS -----------------
@app.route("/teachers")
def teachers():
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, c.name as homeroom_class
            FROM teachers t
            LEFT JOIN classes c ON t.id = c.teacher_id
            ORDER BY t.id ASC
        """)
        teachers_list = cursor.fetchall()
    return render_template("teachers.html", teachers=teachers_list)

@app.route("/teachers/new", methods=["POST"])
def add_teacher():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    qualification = request.form.get("qualification", "").strip()
    subject_specialty = request.form.get("subject_specialty", "").strip()
    join_date = request.form.get("join_date", date.today().strftime("%Y-%m-%d"))

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO teachers (full_name, email, phone, qualification, subject_specialty, join_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (full_name, email, phone, qualification, subject_specialty, join_date))
        conn.commit()

    flash(f"Teacher {full_name} added to the faculty list.", "success")
    return redirect(url_for("teachers"))

@app.route("/teachers/<int:teacher_id>/edit", methods=["POST"])
@login_required
def edit_teacher(teacher_id):
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    qualification = request.form.get("qualification", "").strip()
    subject_specialty = request.form.get("subject_specialty", "").strip()

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE teachers SET full_name = ?, email = ?, phone = ?, qualification = ?, subject_specialty = ?
            WHERE id = ?
        """, (full_name, email, phone, qualification, subject_specialty, teacher_id))
        conn.commit()

    flash(f"Teacher {full_name}'s profile updated successfully.", "success")
    return redirect(url_for("teachers"))

@app.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
@admin_required
def delete_teacher(teacher_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM teachers WHERE id = ?", (teacher_id,))
        teacher = cursor.fetchone()
        teacher_name = teacher["full_name"] if teacher else f"ID {teacher_id}"
        # Unassign from any homeroom classes first
        cursor.execute("UPDATE classes SET teacher_id = NULL WHERE teacher_id = ?", (teacher_id,))
        cursor.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
        conn.commit()

    database.add_security_log("RECORD_DELETED", session.get("username"), request.remote_addr, f"Removed teacher {teacher_name} from faculty roster", "WARNING")
    flash(f"Teacher {teacher_name} has been removed from the faculty roster.", "info")
    return redirect(url_for("teachers"))

# ----------------- CLASSES -----------------
@app.route("/classes")
def classes():
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, t.full_name as teacher_name, COUNT(s.id) as student_count
            FROM classes c
            LEFT JOIN teachers t ON c.teacher_id = t.id
            LEFT JOIN students s ON c.id = s.class_id AND s.status = 'Active'
            GROUP BY c.id
            ORDER BY c.id ASC
        """)
        classes_list = cursor.fetchall()

        cursor.execute("SELECT * FROM teachers WHERE status = 'Active'")
        teachers_list = cursor.fetchall()

    return render_template("classes.html", classes=classes_list, teachers=teachers_list)

@app.route("/classes/new", methods=["POST"])
def add_class():
    name = request.form.get("name", "").strip()
    grade_level = request.form.get("grade_level", "").strip()
    room_number = request.form.get("room_number", "").strip()
    capacity = int(request.form.get("capacity", 25))
    teacher_id = request.form.get("teacher_id") or None

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO classes (name, grade_level, room_number, capacity, teacher_id)
            VALUES (?, ?, ?, ?, ?)
        """, (name, grade_level, room_number, capacity, teacher_id))
        conn.commit()

    flash(f"Class '{name}' created successfully.", "success")
    return redirect(url_for("classes"))

@app.route("/classes/<int:class_id>/edit", methods=["POST"])
@login_required
def edit_class(class_id):
    name = request.form.get("name", "").strip()
    grade_level = request.form.get("grade_level", "").strip()
    room_number = request.form.get("room_number", "").strip()
    capacity = int(request.form.get("capacity", 25))
    teacher_id = request.form.get("teacher_id") or None

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE classes SET name = ?, grade_level = ?, room_number = ?, capacity = ?, teacher_id = ?
            WHERE id = ?
        """, (name, grade_level, room_number, capacity, teacher_id, class_id))
        conn.commit()

    flash(f"Class '{name}' updated successfully.", "success")
    return redirect(url_for("classes"))

@app.route("/classes/<int:class_id>/delete", methods=["POST"])
@admin_required
def delete_class(class_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
        cls = cursor.fetchone()
        class_name = cls["name"] if cls else f"ID {class_id}"

        # Prevent deletion if students are enrolled
        cursor.execute("SELECT COUNT(*) as cnt FROM students WHERE class_id = ?", (class_id,))
        count = cursor.fetchone()["cnt"]
        if count > 0:
            flash(f"Cannot delete '{class_name}': {count} pupil(s) are still enrolled. Reassign them first.", "error")
            return redirect(url_for("classes"))

        cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
        conn.commit()

    database.add_security_log("RECORD_DELETED", session.get("username"), request.remote_addr, f"Deleted class section '{class_name}'", "WARNING")
    flash(f"Class section '{class_name}' has been removed.", "info")
    return redirect(url_for("classes"))

# ----------------- GRADES & REPORT CARDS -----------------
@app.route("/grades")
def grades():
    class_id = request.args.get("class_id")
    term = request.args.get("term", "Term 1 - Fall 2026")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM classes ORDER BY id")
        classes_list = cursor.fetchall()

        if not class_id and classes_list:
            class_id = classes_list[0]["id"]
        elif class_id:
            class_id = int(class_id)

        cursor.execute("SELECT * FROM subjects ORDER BY id")
        subjects_list = cursor.fetchall()

        cursor.execute("""
            SELECT s.id, s.first_name, s.last_name, s.admission_no, c.name as class_name
            FROM students s
            JOIN classes c ON s.class_id = c.id
            WHERE s.class_id = ? AND s.status = 'Active'
            ORDER BY s.last_name ASC
        """, (class_id,))
        students_list = cursor.fetchall()

        # Fetch existing grades
        cursor.execute("""
            SELECT g.*, sub.name as subject_name
            FROM grades g
            JOIN subjects sub ON g.subject_id = sub.id
            WHERE g.term = ?
        """, (term,))
        all_grades = cursor.fetchall()
        
        # Build quick map (student_id, subject_id) -> grade
        grade_map = {}
        for g in all_grades:
            grade_map[(g["student_id"], g["subject_id"])] = g

    return render_template(
        "grades.html",
        classes=classes_list,
        selected_class_id=class_id,
        term=term,
        subjects=subjects_list,
        students=students_list,
        grade_map=grade_map
    )

@app.route("/grades/save", methods=["POST"])
def save_grade():
    student_id = request.form.get("student_id")
    subject_id = request.form.get("subject_id")
    term = request.form.get("term", "Term 1 - Fall 2026")
    score_raw = request.form.get("score")
    conduct = request.form.get("conduct_rating", "Good")
    remarks = request.form.get("teacher_remarks", "").strip()

    try:
        score = float(score_raw)
        letter_grade = database.calculate_letter_grade(score)
    except (ValueError, TypeError):
        flash("Invalid score provided.", "error")
        return redirect(request.referrer or url_for("grades"))

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO grades (student_id, subject_id, term, score, letter_grade, teacher_remarks, conduct_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, subject_id, term) DO UPDATE SET
                score = excluded.score,
                letter_grade = excluded.letter_grade,
                teacher_remarks = excluded.teacher_remarks,
                conduct_rating = excluded.conduct_rating
        """, (student_id, subject_id, term, score, letter_grade, remarks, conduct))
        conn.commit()

    flash("Grade recorded successfully!", "success")
    return redirect(request.referrer or url_for("grades"))

def clean_phone_number(phone_raw):
    """Strips all non-digit characters and normalizes international code."""
    digits = re.sub(r"\D", "", str(phone_raw or ""))
    # If 10 digits (US/Canada local number), prefix with '1'
    if len(digits) == 10:
        return "1" + digits
    return digits

def generate_report_card_message(student, term, grades, avg_score, overall_grade, att, base_url):
    att_present = att["present_cnt"] if att and att["present_cnt"] else 0
    att_total = att["total_days"] if att and att["total_days"] else 0
    att_rate = round((att_present / att_total * 100), 1) if att_total > 0 else 100

    subjects_summary = []
    for g in grades:
        subjects_summary.append(f"• {g['subject_name']}: {int(g['score'])}% ({g['letter_grade']})")
    subjects_text = "\n".join(subjects_summary) if subjects_summary else "• Evaluations pending"

    remarks_summary = ""
    for g in grades:
        if "teacher_remarks" in g.keys() and g["teacher_remarks"]:
            remarks_summary = g["teacher_remarks"]
            break
    if not remarks_summary:
        remarks_summary = "Demonstrates steady focus and curiosity in class."

    report_url = f"{base_url}/report-card/{student['id']}?term={urllib.parse.quote(term)}"

    msg = f"""🏫 *SunnyVale Primary School*
📜 *Official Progress Report Card*
━━━━━━━━━━━━━━━━━━━━
👤 *Pupil:* {student['first_name']} {student['last_name']} ({student['admission_no']})
🎒 *Class:* {student['class_name']} ({student['grade_level']})
📅 *Term:* {term}
👩‍🏫 *Homeroom:* {student['homeroom_teacher'] or 'Faculty Staff'}

📊 *Academic Performance:*
Overall Average: {avg_score}% ({overall_grade})
{subjects_text}

📅 *Attendance:* {att_rate}% ({att_present} days present)

💬 *Educator Note:*
"{remarks_summary}"

🔗 *View Full Report Online:*
{report_url}
━━━━━━━━━━━━━━━━━━━━
Dear {student['guardian_name']}, thank you for supporting your child's learning journey!"""
    return msg

@app.route("/report-card/<int:student_id>")
def report_card(student_id):
    term = request.args.get("term", "Term 1 - Fall 2026")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.name as class_name, c.grade_level, t.full_name as homeroom_teacher
            FROM students s
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN teachers t ON c.teacher_id = t.id
            WHERE s.id = ?
        """, (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("students"))

        # Grades for this term
        cursor.execute("""
            SELECT g.*, sub.name as subject_name, sub.code as subject_code
            FROM grades g
            JOIN subjects sub ON g.subject_id = sub.id
            WHERE g.student_id = ? AND g.term = ?
            ORDER BY sub.name ASC
        """, (student_id, term))
        grades = cursor.fetchall()

        # Compute term average
        avg_score = 0
        overall_grade = "N/A"
        if grades:
            avg_score = round(sum(g["score"] for g in grades) / len(grades), 1)
            overall_grade = database.calculate_letter_grade(avg_score)

        # Attendance summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_cnt,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_cnt,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_cnt,
                SUM(CASE WHEN status = 'Excused' THEN 1 ELSE 0 END) as excused_cnt
            FROM attendance
            WHERE student_id = ?
        """, (student_id,))
        att = cursor.fetchone()

        # Communication Logs
        cursor.execute("""
            SELECT * FROM communication_logs 
            WHERE student_id = ? 
            ORDER BY sent_at DESC LIMIT 10
        """, (student_id,))
        comm_logs = cursor.fetchall()

    # Generate message for WhatsApp & SMS
    base_url = request.host_url.rstrip("/")
    message_text = generate_report_card_message(student, term, grades, avg_score, overall_grade, att, base_url)
    clean_phone = clean_phone_number(student["guardian_phone"])
    encoded_message = urllib.parse.quote(message_text)

    whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"
    sms_url = f"sms:{clean_phone}?body={encoded_message}"

    return render_template(
        "report_card.html",
        student=student,
        term=term,
        grades=grades,
        avg_score=avg_score,
        overall_grade=overall_grade,
        att=att,
        message_text=message_text,
        clean_phone=clean_phone,
        whatsapp_url=whatsapp_url,
        sms_url=sms_url,
        comm_logs=comm_logs
    )

@app.route("/api/report-card/<int:student_id>/log-dispatch", methods=["POST"])
def log_report_card_dispatch(student_id):
    channel = request.form.get("channel", "WhatsApp")
    phone = request.form.get("phone", "")
    recipient = request.form.get("recipient_name", "")
    message_content = request.form.get("message_content", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO communication_logs (student_id, channel, recipient_name, recipient_phone, message_content, sent_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Dispatched')
        """, (student_id, channel, recipient, phone, message_content, now_str))
        conn.commit()

    flash(f"Report card logged as dispatched via {channel} to {recipient} ({phone})!", "success")
    return redirect(request.referrer or url_for("report_card", student_id=student_id))

@app.route("/api/report-card/<int:student_id>/preview-data")
def report_card_preview_data(student_id):
    term = request.args.get("term", "Term 1 - Fall 2026")
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.name as class_name, c.grade_level, t.full_name as homeroom_teacher
            FROM students s
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN teachers t ON c.teacher_id = t.id
            WHERE s.id = ?
        """, (student_id,))
        student = cursor.fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        cursor.execute("""
            SELECT g.*, sub.name as subject_name
            FROM grades g
            JOIN subjects sub ON g.subject_id = sub.id
            WHERE g.student_id = ? AND g.term = ?
        """, (student_id, term))
        grades = cursor.fetchall()

        avg_score = round(sum(g["score"] for g in grades) / len(grades), 1) if grades else 0
        overall_grade = database.calculate_letter_grade(avg_score) if grades else "N/A"

        cursor.execute("SELECT COUNT(*) as total_days, SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_cnt FROM attendance WHERE student_id = ?", (student_id,))
        att = cursor.fetchone()

    base_url = request.host_url.rstrip("/")
    message_text = generate_report_card_message(student, term, grades, avg_score, overall_grade, att, base_url)
    clean_phone = clean_phone_number(student["guardian_phone"])
    encoded_message = urllib.parse.quote(message_text)

    return jsonify({
        "student_name": f"{student['first_name']} {student['last_name']}",
        "guardian_name": student["guardian_name"],
        "guardian_phone": student["guardian_phone"],
        "clean_phone": clean_phone,
        "message_text": message_text,
        "whatsapp_url": f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_message}",
        "sms_url": f"sms:{clean_phone}?body={encoded_message}"
    })

# ----------------- FEES & BILLING -----------------
@app.route("/fees")
def fees():
    status_filter = request.args.get("status", "")
    with database.get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT f.*, s.first_name, s.last_name, s.admission_no, c.name as class_name
            FROM fees f
            JOIN students s ON f.student_id = s.id
            JOIN classes c ON s.class_id = c.id
            WHERE 1=1
        """
        params = []
        if status_filter:
            query += " AND f.status = ?"
            params.append(status_filter)

        query += " ORDER BY f.due_date ASC, f.id DESC"
        cursor.execute(query, params)
        fee_records = cursor.fetchall()

        # All active students for invoice issuance
        cursor.execute("SELECT id, first_name, last_name, admission_no FROM students WHERE status = 'Active' ORDER BY last_name")
        students = cursor.fetchall()

        # Summary
        cursor.execute("""
            SELECT 
                COALESCE(SUM(amount), 0) as total,
                COALESCE(SUM(paid_amount), 0) as paid,
                COALESCE(SUM(amount - paid_amount), 0) as balance
            FROM fees
        """)
        summary = cursor.fetchone()

    return render_template(
        "fees.html",
        fees=fee_records,
        students=students,
        summary=summary,
        selected_status=status_filter
    )

@app.route("/fees/new", methods=["POST"])
def add_fee():
    student_id = request.form.get("student_id")
    fee_type = request.form.get("fee_type")
    amount = float(request.form.get("amount", 0.0))
    due_date = request.form.get("due_date", date.today().strftime("%Y-%m-%d"))

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, ?, ?, 0.0, ?, 'Pending')
        """, (student_id, fee_type, amount, due_date))
        conn.commit()

    flash("Fee invoice created successfully.", "success")
    return redirect(url_for("fees"))

@app.route("/fees/<int:fee_id>/pay", methods=["POST"])
def pay_fee(fee_id):
    payment_amount = float(request.form.get("payment_amount", 0.0))
    payment_method = request.form.get("payment_method", "Bank Transfer")
    payment_date = date.today().strftime("%Y-%m-%d")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fees WHERE id = ?", (fee_id,))
        fee = cursor.fetchone()
        if not fee:
            flash("Fee record not found.", "error")
            return redirect(url_for("fees"))

        new_paid = fee["paid_amount"] + payment_amount
        if new_paid >= fee["amount"]:
            new_status = "Paid"
            new_paid = fee["amount"]
        else:
            new_status = "Partial"

        cursor.execute("""
            UPDATE fees SET
                paid_amount = ?,
                status = ?,
                payment_date = ?,
                payment_method = ?
            WHERE id = ?
        """, (new_paid, new_status, payment_date, payment_method, fee_id))
        conn.commit()

    flash(f"Payment of ${payment_amount:.2f} recorded successfully!", "success")
    return redirect(request.referrer or url_for("fees"))

@app.route("/fees/<int:fee_id>/delete", methods=["POST"])
@admin_required
def delete_fee(fee_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.fee_type, s.first_name, s.last_name
            FROM fees f JOIN students s ON f.student_id = s.id
            WHERE f.id = ?
        """, (fee_id,))
        fee = cursor.fetchone()
        desc = f"{fee['fee_type']} for {fee['first_name']} {fee['last_name']}" if fee else f"ID {fee_id}"
        cursor.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
        conn.commit()

    database.add_security_log("RECORD_DELETED", session.get("username"), request.remote_addr, f"Deleted fee invoice: {desc}", "WARNING")
    flash(f"Fee invoice ({desc}) deleted.", "info")
    return redirect(url_for("fees"))

@app.route("/fees/<int:fee_id>/receipt")
def fee_receipt(fee_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, s.first_name, s.last_name, s.admission_no, s.guardian_name, s.guardian_phone,
                   c.name as class_name
            FROM fees f
            JOIN students s ON f.student_id = s.id
            JOIN classes c ON s.class_id = c.id
            WHERE f.id = ?
        """, (fee_id,))
        fee = cursor.fetchone()
        if not fee:
            flash("Receipt not found.", "error")
            return redirect(url_for("fees"))

    return render_template("fee_receipt.html", fee=fee)

# ----------------- NOTICES & ANNOUNCEMENTS -----------------
@app.route("/notices")
def notices():
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notices ORDER BY date_posted DESC, id DESC")
        notices_list = cursor.fetchall()
    return render_template("notices.html", notices=notices_list)

@app.route("/notices/new", methods=["POST"])
def add_notice():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    audience = request.form.get("audience", "All")
    priority = request.form.get("priority", "Normal")
    date_posted = date.today().strftime("%Y-%m-%d")

    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notices (title, content, audience, priority, date_posted)
            VALUES (?, ?, ?, ?, ?)
        """, (title, content, audience, priority, date_posted))
        conn.commit()

    flash("Announcement published successfully to the school board.", "success")
    return redirect(url_for("notices"))

@app.route("/notices/<int:notice_id>/delete", methods=["POST"])
def delete_notice(notice_id):
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
        conn.commit()
    flash("Notice removed.", "info")
    return redirect(url_for("notices"))

# ----------------- ADMIN CONTROL CENTER -----------------
@app.route("/admin/users")
@admin_required
def admin_users():
    users_list = database.get_all_users()
    settings = database.get_school_settings()
    security_logs = database.get_security_logs(limit=30)
    return render_template("admin_users.html", users=users_list, settings=settings, security_logs=security_logs)

@app.route("/admin/users/new", methods=["POST"])
@admin_required
def admin_create_user():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "Teacher")

    if not username or not password or not full_name:
        flash("Username, password, and full name are required.", "error")
        return redirect(url_for("admin_users"))

    # Enforce password policy
    valid, msg = validate_password_strength(password)
    if not valid:
        flash(f"Password Policy Error: {msg}", "error")
        return redirect(url_for("admin_users"))

    existing = database.get_user_by_username(username)
    if existing:
        flash(f"User account @{username} already exists. Please choose a different username.", "error")
        return redirect(url_for("admin_users"))

    database.create_user(username, password, full_name, email, role)
    database.add_security_log("USER_CREATED", session.get("username"), request.remote_addr, f"Created account @{username} ({full_name}) with {role} role", "INFO")
    flash(f"User account @{username} ({full_name}) created successfully with {role} role!", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/<int:user_id>/password", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("New password cannot be empty.", "error")
        return redirect(url_for("admin_users"))

    valid, msg = validate_password_strength(new_password)
    if not valid:
        flash(f"Password Policy Error: {msg}", "error")
        return redirect(url_for("admin_users"))

    database.update_user_password(user_id, new_password)
    database.add_security_log("PASSWORD_CHANGED", session.get("username"), request.remote_addr, f"Reset password for user ID {user_id}", "WARNING")
    flash("Password updated successfully for account.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("Cannot delete your own active administrator account.", "error")
        return redirect(url_for("admin_users"))

    database.delete_user(user_id)
    database.add_security_log("USER_DELETED", session.get("username"), request.remote_addr, f"Revoked and deleted user ID {user_id}", "DANGER")
    flash("User account was successfully removed from the system.", "info")
    return redirect(url_for("admin_users"))

@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_update_settings():
    new_settings = {
        "school_name": request.form.get("school_name", "").strip(),
        "school_tagline": request.form.get("school_tagline", "").strip(),
        "academic_year": request.form.get("academic_year", "").strip(),
        "current_term": request.form.get("current_term", "").strip(),
        "principal_name": request.form.get("principal_name", "").strip(),
        "contact_phone": request.form.get("contact_phone", "").strip(),
        "contact_email": request.form.get("contact_email", "").strip(),
    }
    database.update_school_settings(new_settings)
    database.add_security_log("SETTINGS_UPDATED", session.get("username"), request.remote_addr, "Global school profile settings modified", "INFO")
    flash("School profile settings updated successfully!", "success")
    return redirect(url_for("admin_users"))

if __name__ == "__main__":
    print("=" * 60)
    print(" * SunnyVale Primary School Management System")
    print(" * Running on: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)

