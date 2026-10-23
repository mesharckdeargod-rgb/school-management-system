import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "school.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            qualification TEXT,
            subject_specialty TEXT,
            join_date TEXT,
            status TEXT DEFAULT 'Active'
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            room_number TEXT,
            capacity INTEGER DEFAULT 30,
            teacher_id INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE SET NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_no TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            gender TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            guardian_name TEXT NOT NULL,
            guardian_relation TEXT NOT NULL,
            guardian_phone TEXT NOT NULL,
            guardian_email TEXT,
            home_address TEXT,
            emergency_contact TEXT,
            medical_allergies TEXT DEFAULT 'None',
            enrollment_date TEXT,
            status TEXT DEFAULT 'Active',
            avatar_color TEXT DEFAULT 'bg-indigo-100 text-indigo-700',
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE RESTRICT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL, -- 'Present', 'Absent', 'Late', 'Excused'
            remarks TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            UNIQUE(student_id, date)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            term TEXT NOT NULL,
            score REAL NOT NULL,
            letter_grade TEXT NOT NULL,
            teacher_remarks TEXT,
            conduct_rating TEXT DEFAULT 'Good',
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
            UNIQUE(student_id, subject_id, term)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            fee_type TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_amount REAL DEFAULT 0.0,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending', -- 'Paid', 'Partial', 'Pending'
            payment_date TEXT,
            payment_method TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            audience TEXT DEFAULT 'All',
            priority TEXT DEFAULT 'Normal',
            date_posted TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS communication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            channel TEXT NOT NULL, -- 'WhatsApp', 'SMS'
            recipient_name TEXT NOT NULL,
            recipient_phone TEXT NOT NULL,
            message_content TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT DEFAULT 'Sent',
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'Admin', -- 'Admin', 'Teacher', 'Staff'
            created_at TEXT NOT NULL,
            last_login TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS school_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL, -- 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOCKED_OUT', 'PASSWORD_CHANGED', 'USER_CREATED', 'RECORD_DELETED'
            username TEXT,
            ip_address TEXT,
            description TEXT,
            severity TEXT DEFAULT 'INFO' -- 'INFO', 'WARNING', 'DANGER'
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            ip_address TEXT PRIMARY KEY,
            failed_count INTEGER DEFAULT 0,
            last_failed_at TEXT,
            locked_until TEXT
        )
        """)

        conn.commit()

    seed_users_and_settings()
    ensure_creche_kg_class_1_to_6()

def ensure_creche_kg_class_1_to_6():
    standard_classes = [
        ("Crèche - Little Angels", "Crèche", "Room 100", 15, 1),
        ("Kindergarten - Sunflowers", "Kindergarten", "Room 101", 20, 1),
        ("Class 1 - Bluebirds", "Class 1", "Room 102", 24, 2),
        ("Class 2 - Dolphins", "Class 2", "Room 103", 25, 3),
        ("Class 3 - Redwoods", "Class 3", "Room 201", 25, 4),
        ("Class 4 - Explorers", "Class 4", "Room 202", 28, 5),
        ("Class 5 - Champions", "Class 5", "Room 203", 30, 2),
        ("Class 6 - Pioneers", "Class 6", "Room 204", 30, 3),
    ]
    with get_db() as conn:
        cursor = conn.cursor()
        # Rename any old "Grade X" references to "Class X"
        for i in range(1, 7):
            cursor.execute("UPDATE classes SET grade_level = ?, name = ? WHERE grade_level = ?", (f"Class {i}", f"Class {i} - Section A", f"Grade {i}"))
        
        for name, grade, room, cap, tid in standard_classes:
            cursor.execute("SELECT id FROM classes WHERE grade_level = ?", (grade,))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE classes SET name = ?, room_number = ?, capacity = ? WHERE id = ?
                """, (name, room, cap, row["id"]))
            else:
                cursor.execute("""
                    INSERT INTO classes (name, grade_level, room_number, capacity, teacher_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, grade, room, cap, tid))
        conn.commit()

def seed_users_and_settings():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Seed Admin user if not exists
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE username = 'admin'")
        if cursor.fetchone()["cnt"] == 0:
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, email, role, created_at)
                VALUES (?, ?, ?, ?, 'Admin', ?)
            """, (
                "admin",
                generate_password_hash("admin123"),
                "Dr. Eleanor Vance (Principal & Admin)",
                "principal@sunnyvale.edu",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        # Seed sample Teacher user if not exists
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE username = 'teacher'")
        if cursor.fetchone()["cnt"] == 0:
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, email, role, created_at)
                VALUES (?, ?, ?, ?, 'Teacher', ?)
            """, (
                "teacher",
                generate_password_hash("teacher123"),
                "Sarah Jenkins (Homeroom Teacher)",
                "s.jenkins@sunnyvale.edu",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        # Seed Default School Settings if not set
        default_settings = [
            ("school_name", "SunnyVale Primary School"),
            ("school_tagline", "Nurturing Curious Minds & Bright Futures"),
            ("academic_year", "2026 - 2027"),
            ("current_term", "Term 1 - Fall 2026"),
            ("principal_name", "Dr. Eleanor Vance, Ed.D"),
            ("contact_phone", "+1 (555) 234-5670"),
            ("contact_email", "office@sunnyvale.edu"),
            ("campus_address", "100 Sunshine Way, Springfield"),
        ]
        for key, val in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO school_settings (key, value)
                VALUES (?, ?)
            """, (key, val))

        conn.commit()

def get_user_by_username(username):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),))
        return cursor.fetchone()

def get_user_by_id(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()

def get_all_users():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, email, role, created_at, last_login FROM users ORDER BY id ASC")
        return cursor.fetchall()

def create_user(username, password, full_name, email, role="Teacher"):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            username.strip().lower(),
            generate_password_hash(password),
            full_name.strip(),
            email.strip(),
            role,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        return cursor.lastrowid

def update_user_password(user_id, new_password):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
        conn.commit()

def update_last_login(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()

def delete_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

def get_school_settings():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM school_settings")
        rows = cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}

def update_school_settings(settings_dict):
    with get_db() as conn:
        cursor = conn.cursor()
        for k, v in settings_dict.items():
            cursor.execute("""
                INSERT INTO school_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (k, str(v).strip()))
        conn.commit()

def is_ip_locked(ip_address):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT locked_until FROM login_attempts WHERE ip_address = ?", (ip_address,))
        row = cursor.fetchone()
        if not row or not row["locked_until"]:
            return False, 0
        
        now = datetime.now()
        try:
            locked_until = datetime.strptime(row["locked_until"], "%Y-%m-%d %H:%M:%S")
            if now < locked_until:
                remaining_mins = max(1, int((locked_until - now).total_seconds() / 60))
                return True, remaining_mins
        except Exception:
            pass
        return False, 0

def record_login_failure(ip_address, username):
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT failed_count FROM login_attempts WHERE ip_address = ?", (ip_address,))
        row = cursor.fetchone()
        
        count = (row["failed_count"] if row else 0) + 1
        locked_until = None
        
        if count >= 5:
            locked_until_dt = now + timedelta(minutes=15)
            locked_until = locked_until_dt.strftime("%Y-%m-%d %H:%M:%S")
            add_security_log("LOCKED_OUT", username, ip_address, f"IP locked for 15 mins after {count} consecutive failed attempts", "DANGER")
        else:
            add_security_log("LOGIN_FAILED", username, ip_address, f"Failed password attempt ({count}/5)", "WARNING")
            
        cursor.execute("""
            INSERT INTO login_attempts (ip_address, failed_count, last_failed_at, locked_until)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ip_address) DO UPDATE SET
                failed_count = excluded.failed_count,
                last_failed_at = excluded.last_failed_at,
                locked_until = excluded.locked_until
        """, (ip_address, count, now_str, locked_until))
        conn.commit()
        return count, locked_until is not None

def record_login_success(ip_address, username):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE ip_address = ?", (ip_address,))
        conn.commit()
    add_security_log("LOGIN_SUCCESS", username, ip_address, f"Successful authentication for user @{username}", "INFO")

def add_security_log(event_type, username, ip_address, description, severity="INFO"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_logs (timestamp, event_type, username, ip_address, description, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now_str, event_type, username or "Anonymous", ip_address or "Unknown", description, severity))
        conn.commit()

def get_security_logs(limit=30):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM security_logs ORDER BY id DESC LIMIT ?", (limit,))
        return cursor.fetchall()

def calculate_letter_grade(score):
    if score >= 90: return 'A+'
    elif score >= 80: return 'A'
    elif score >= 70: return 'B'
    elif score >= 60: return 'C'
    elif score >= 50: return 'D'
    else: return 'F'

def seed_data_if_empty():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM students")
        if cursor.fetchone()['cnt'] > 0:
            return  # already seeded

        # Seed Teachers
        teachers = [
            ("Sarah Jenkins", "s.jenkins@littlepines.edu", "+1 (555) 234-5671", "B.Ed in Early Childhood", "Homeroom & Literacy", "2022-08-15"),
            ("Michael Chang", "m.chang@littlepines.edu", "+1 (555) 234-5672", "B.Sc Elementary Math & Science", "STEM & Arithmetic", "2021-08-10"),
            ("Emily Roberts", "e.roberts@littlepines.edu", "+1 (555) 234-5673", "M.A. in Primary Education", "English & Phonics", "2020-07-20"),
            ("David Miller", "d.miller@littlepines.edu", "+1 (555) 234-5674", "B.A. in Fine Arts & Education", "Art & Creative Crafts", "2023-01-10"),
            ("Amina Patel", "a.patel@littlepines.edu", "+1 (555) 234-5675", "B.Ed Physical Education", "Physical Education & Health", "2022-09-01"),
        ]
        cursor.executemany("""
            INSERT INTO teachers (full_name, email, phone, qualification, subject_specialty, join_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, teachers)

        # Seed Classes
        classes = [
            ("Crèche - Little Angels", "Crèche", "Room 100", 15, 1),
            ("Kindergarten - Sunflowers", "Kindergarten", "Room 101", 20, 1),
            ("Class 1 - Bluebirds", "Class 1", "Room 102", 24, 2),
            ("Class 2 - Dolphins", "Class 2", "Room 103", 25, 3),
            ("Class 3 - Redwoods", "Class 3", "Room 201", 25, 4),
            ("Class 4 - Explorers", "Class 4", "Room 202", 28, 5),
            ("Class 5 - Champions", "Class 5", "Room 203", 30, 2),
            ("Class 6 - Pioneers", "Class 6", "Room 204", 30, 3),
        ]
        cursor.executemany("""
            INSERT INTO classes (name, grade_level, room_number, capacity, teacher_id)
            VALUES (?, ?, ?, ?, ?)
        """, classes)

        # Seed Subjects
        subjects = [
            ("English & Phonics", "ENG-101"),
            ("Mathematics", "MATH-101"),
            ("General Science", "SCI-101"),
            ("Social Studies & Civics", "SOC-101"),
            ("Art & Crafts", "ART-101"),
            ("Physical Education & Health", "PE-101"),
            ("Music & Rhythm", "MUS-101"),
        ]
        cursor.executemany("""
            INSERT INTO subjects (name, code)
            VALUES (?, ?)
        """, subjects)

        avatar_colors = [
            "bg-blue-100 text-blue-700",
            "bg-emerald-100 text-emerald-700",
            "bg-purple-100 text-purple-700",
            "bg-amber-100 text-amber-700",
            "bg-rose-100 text-rose-700",
            "bg-cyan-100 text-cyan-700",
            "bg-indigo-100 text-indigo-700",
        ]

        students = [
            ("STU-2026-001", "Lucas", "Bennett", "2020-04-12", "Male", 1, "Eleanor Bennett", "Mother", "+1 (555) 301-1101", "eleanor.b@example.com", "14 Maple Street, Springfield", "+1 (555) 301-1102", "Mild Peanut allergy", "2026-09-01", avatar_colors[0]),
            ("STU-2026-002", "Mia", "Johnson", "2020-09-25", "Female", 1, "Marcus Johnson", "Father", "+1 (555) 301-1103", "marcus.j@example.com", "28 Oak Avenue, Springfield", "+1 (555) 301-1104", "None", "2026-09-01", avatar_colors[1]),
            ("STU-2026-003", "Ethan", "Williams", "2019-02-18", "Male", 2, "Sophia Williams", "Mother", "+1 (555) 301-1105", "sophia.w@example.com", "82 Pine Hill Rd, Springfield", "+1 (555) 301-1106", "Asthma inhaler in backpack", "2025-09-01", avatar_colors[2]),
            ("STU-2026-004", "Olivia", "Garcia", "2019-11-04", "Female", 2, "Carlos Garcia", "Father", "+1 (555) 301-1107", "carlos.g@example.com", "105 Elm Boulevard, Springfield", "+1 (555) 301-1108", "None", "2025-09-01", avatar_colors[3]),
            ("STU-2026-005", "Noah", "Brown", "2018-07-15", "Male", 3, "Linda Brown", "Mother", "+1 (555) 301-1109", "linda.b@example.com", "47 Willow Way, Springfield", "+1 (555) 301-1110", "Lactose intolerant", "2024-09-01", avatar_colors[4]),
            ("STU-2026-006", "Ava", "Davis", "2018-03-30", "Female", 3, "Robert Davis", "Father", "+1 (555) 301-1111", "robert.d@example.com", "63 Cedar Court, Springfield", "+1 (555) 301-1112", "None", "2024-09-01", avatar_colors[5]),
            ("STU-2026-007", "Liam", "Martinez", "2017-08-22", "Male", 4, "Elena Martinez", "Mother", "+1 (555) 301-1113", "elena.m@example.com", "19 Birch Lane, Springfield", "+1 (555) 301-1114", "Bee sting sensitivity (EpiPen)", "2023-09-01", avatar_colors[6]),
            ("STU-2026-008", "Emma", "Rodriguez", "2017-12-05", "Female", 4, "Mateo Rodriguez", "Father", "+1 (555) 301-1115", "mateo.r@example.com", "304 Magnolia Drive, Springfield", "+1 (555) 301-1116", "None", "2023-09-01", avatar_colors[0]),
            ("STU-2026-009", "Mason", "Taylor", "2016-05-14", "Male", 5, "Rachel Taylor", "Mother", "+1 (555) 301-1117", "rachel.t@example.com", "55 Sunset Ridge, Springfield", "+1 (555) 301-1118", "None", "2022-09-01", avatar_colors[1]),
            ("STU-2026-010", "Charlotte", "Anderson", "2015-10-19", "Female", 6, "James Anderson", "Father", "+1 (555) 301-1119", "james.a@example.com", "77 Brookside Terrace, Springfield", "+1 (555) 301-1120", "None", "2021-09-01", avatar_colors[2]),
            ("STU-2026-011", "Benjamin", "Thomas", "2019-06-11", "Male", 2, "Grace Thomas", "Mother", "+1 (555) 301-1121", "grace.t@example.com", "91 Meadowbrook Rd, Springfield", "+1 (555) 301-1122", "None", "2025-09-01", avatar_colors[3]),
            ("STU-2026-012", "Harper", "Jackson", "2018-09-08", "Female", 3, "Derek Jackson", "Father", "+1 (555) 301-1123", "derek.j@example.com", "12 Orchard Street, Springfield", "+1 (555) 301-1124", "None", "2024-09-01", avatar_colors[4]),
        ]

        cursor.executemany("""
            INSERT INTO students (
                admission_no, first_name, last_name, date_of_birth, gender,
                class_id, guardian_name, guardian_relation, guardian_phone,
                guardian_email, home_address, emergency_contact, medical_allergies,
                enrollment_date, avatar_color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, students)

        today = date.today()
        dates = [today - timedelta(days=i) for i in range(5)]
        
        attendance_records = []
        for d in dates:
            d_str = d.strftime("%Y-%m-%d")
            for s_id in range(1, 13):
                if s_id == 1 and d == dates[1]:
                    status = "Absent"
                    remarks = "Mild fever"
                elif s_id == 3 and d == dates[0]:
                    status = "Late"
                    remarks = "Arrived 8:35 AM"
                elif s_id == 7 and d == dates[2]:
                    status = "Excused"
                    remarks = "Doctor appointment"
                else:
                    status = "Present"
                    remarks = ""
                attendance_records.append((s_id, d_str, status, remarks))

        cursor.executemany("""
            INSERT OR IGNORE INTO attendance (student_id, date, status, remarks)
            VALUES (?, ?, ?, ?)
        """, attendance_records)

        sample_scores = [
            (1, 1, 92, "A+", "Lucas participates enthusiastically in reading aloud.", "Excellent"),
            (1, 2, 88, "A", "Grasps basic counting and pattern concepts very quickly.", "Good"),
            (1, 5, 95, "A+", "Vibrant creativity in finger painting and origami.", "Excellent"),
            (2, 1, 94, "A+", "Remarkable phonics fluency and vocabulary for Kindergarten.", "Excellent"),
            (2, 2, 91, "A+", "Solves spatial puzzles with confidence.", "Excellent"),
            (3, 1, 85, "A", "Shows continuous improvement in spelling tests.", "Good"),
            (3, 2, 78, "B", "Practicing two-digit addition with carryover.", "Good"),
            (3, 3, 90, "A+", "Loves nature exploration and science experiments.", "Excellent"),
            (4, 1, 89, "A", "Active contributor in story circle time.", "Good"),
            (4, 2, 92, "A+", "Very quick with mental arithmetic.", "Excellent"),
            (4, 3, 86, "A", "Shows curiosity during plant life cycle unit.", "Good"),
            (5, 2, 84, "A", "Solid performance on multiplication tables.", "Good"),
            (5, 3, 89, "A", "Excellent science project on solar energy.", "Excellent"),
            (5, 4, 91, "A+", "Thorough understanding of community helpers.", "Excellent"),
            (6, 1, 96, "A+", "Outstanding creative writing essay.", "Excellent"),
            (6, 2, 90, "A+", "High accuracy in division problems.", "Excellent"),
            (7, 3, 93, "A+", "Fascinated by electric circuits lab.", "Excellent"),
            (7, 4, 87, "A", "Well-prepared map geography presentation.", "Good"),
            (8, 1, 91, "A+", "Eloquent reading comprehension summaries.", "Excellent"),
            (8, 2, 85, "A", "Consistent homework completion and neat handwriting.", "Good"),
            (9, 2, 94, "A+", "Top score in geometry and fraction assessment.", "Excellent"),
            (9, 3, 92, "A+", "Meticulous science notebook records.", "Excellent"),
            (10, 1, 95, "A+", "Excellent leadership during group book club.", "Excellent"),
            (10, 2, 98, "A+", "Advanced mathematical problem solving.", "Excellent"),
            (10, 6, 92, "A+", "Outstanding team spirit in track and field.", "Excellent"),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO grades (student_id, subject_id, score, letter_grade, teacher_remarks, conduct_rating, term)
            VALUES (?, ?, ?, ?, ?, ?, 'Term 1 - Fall 2026')
        """, sample_scores)

        fees = [
            (1, "Term 1 Tuition", 1200.0, 1200.0, "2026-09-15", "Paid", "2026-09-10", "Bank Transfer"),
            (1, "Hot Lunch Meal Plan", 350.0, 350.0, "2026-09-20", "Paid", "2026-09-12", "Card"),
            (2, "Term 1 Tuition", 1200.0, 1200.0, "2026-09-15", "Paid", "2026-09-08", "Card"),
            (2, "School Bus Transport", 250.0, 125.0, "2026-09-25", "Partial", "2026-09-22", "Cash"),
            (3, "Term 1 Tuition", 1250.0, 1250.0, "2026-09-15", "Paid", "2026-09-14", "Bank Transfer"),
            (3, "Art & Lab Materials", 100.0, 0.0, "2026-10-30", "Pending", None, None),
            (4, "Term 1 Tuition", 1250.0, 1250.0, "2026-09-15", "Paid", "2026-09-10", "Card"),
            (5, "Term 1 Tuition", 1300.0, 650.0, "2026-09-15", "Partial", "2026-09-18", "Bank Transfer"),
            (6, "Term 1 Tuition", 1300.0, 1300.0, "2026-09-15", "Paid", "2026-09-05", "Card"),
            (7, "Term 1 Tuition", 1350.0, 0.0, "2026-09-15", "Pending", None, None),
            (7, "School Bus Transport", 250.0, 0.0, "2026-10-15", "Pending", None, None),
            (8, "Term 1 Tuition", 1350.0, 1350.0, "2026-09-15", "Paid", "2026-09-11", "Bank Transfer"),
            (9, "Term 1 Tuition", 1400.0, 1400.0, "2026-09-15", "Paid", "2026-09-14", "Card"),
            (10, "Term 1 Tuition", 1400.0, 1400.0, "2026-09-15", "Paid", "2026-09-09", "Bank Transfer"),
            (11, "Term 1 Tuition", 1250.0, 1250.0, "2026-09-15", "Paid", "2026-09-12", "Card"),
            (12, "Term 1 Tuition", 1300.0, 0.0, "2026-10-25", "Pending", None, None),
        ]
        cursor.executemany("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, payment_date, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, fees)

        notices = [
            ("Annual Sports Day 2026 Announcement", "We are delighted to invite all parents and guardians to our Annual Primary Sports Day on Friday, November 14th. Fun obstacle races, track sprints, and tug of war!", "All", "High", "2026-10-18"),
            ("Parent-Teacher Conference (Term 1)", "Term 1 Parent-Teacher Conferences will take place on October 30th and 31st. Individual 15-minute appointment booking sheets have been sent home via student backpacks.", "Parents", "High", "2026-10-15"),
            ("Halloween Costume Parade & Book Fair", "Students in Kindergarten through Grade 5 may dress as their favorite storybook character on Friday, October 31st. The Scholastic Book Fair will run in the library all week.", "All", "Normal", "2026-10-12"),
            ("Winter Uniform Transition Notice", "Starting Monday, November 3rd, students should transition to the official winter navy cardigan/sweater and full trousers. Available at the campus uniform desk.", "Parents", "Normal", "2026-10-08"),
            ("Staff Professional Development Day", "Reminder to all faculty members: Friday, November 7th is a pupil-free day dedicated to early childhood literacy workshops.", "Teachers", "Low", "2026-10-05"),
        ]
        cursor.executemany("""
            INSERT INTO notices (title, content, audience, priority, date_posted)
            VALUES (?, ?, ?, ?, ?)
        """, notices)

        conn.commit()
