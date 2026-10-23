# 🏫 SunnyVale Primary School Management System

A modern, comprehensive, and intuitive School Management System tailored specifically for **Primary / Elementary Schools (Kindergarten to Grade 5)**. Built with Python, Flask, SQLite, and Tailwind CSS.

---

## 🌟 Key Features

### 1. 🎒 Primary Pupil & Enrollment Management
- **Detailed Pupil Profiles**: First name, last name, admission ID (e.g. `STU-2026-001`), DOB, gender, status, and custom avatar initials.
- **Child Health & Dietary Tracking**: Prominent tracking for food allergies (e.g. peanut allergy, lactose intolerance), asthma inhalers, and emergency medical notes.
- **Family Contacts**: Guardian name, relation (Mother/Father/Guardian), primary phone, email, residential address, and backup emergency numbers.
- **Search & Filtering**: Search in real-time by pupil name, ID, or guardian, and filter by primary grade level.

### 2. 📅 Classroom Roll Call & Daily Attendance
- **Fast Daily Attendance**: Filter by homeroom class and date.
- **One-Click "Mark All Present"**: Quick roll call for primary school teachers.
- **Attendance States**: Present, Late, Absent, and Excused with custom observation remarks.
- **Cumulative Metrics**: Pupil attendance percentage and historical log cards.

### 3. 🏆 Primary Academic Evaluations & Report Cards
- **Primary Subjects**: English & Phonics, Mathematics, General Science, Social Studies, Art & Crafts, Physical Education, and Music.
- **Holistic Assessment**: Percentage score, letter grade (A+, A, B, C, D, F), classroom conduct rating (Excellent, Good, Satisfactory, Needs Support), and teacher observations.
- **📱 Send Report Cards via WhatsApp & SMS**:
  - **1-Click WhatsApp Delivery**: Opens WhatsApp / WhatsApp Web with a formatted, emoji-enhanced report card summary and direct link pre-addressed to the parent's phone.
  - **1-Click SMS Delivery**: Pre-populates the device SMS app via the `sms:` protocol.
  - **Dispatch Audit Trail**: Logs timestamp, channel, and message content to `communication_logs` for transparency.
  - **Quick Copy**: Allows teachers to copy the text to their clipboard with one click.
- **Official Printable Report Card**:
  - School banner & accreditation details
  - Subject scores, conduct, and teacher commentary
  - Primary developmental competencies checklist (works well with peers, listens attentively, respects property)
  - Signature lines for Homeroom Teacher, Principal, and Parent
  - Print-ready with CSS `@media print` layout.

### 4. 📚 Classes & Homeroom Allocations
- Grade levels: Kindergarten through Grade 5.
- Class section names (e.g., *Kindergarten - Sunflowers*, *Grade 1 - Bluebirds*).
- Room numbers, educator assignments, and student capacity progress bars.

### 5. 👩‍🏫 Faculty & Educator Directory
- Teacher profiles, qualifications (e.g., *B.Ed in Early Childhood*), subject specialties, and assigned homeroom classes.

### 6. 💳 Tuition & Fee Billing
- Fee categories: Term Tuition, Hot Lunch Meal Plan, School Bus Transportation, Uniform & Physical Ed Kits, and Field Trips.
- Statuses: **Paid**, **Partial**, and **Pending**.
- One-click payment modal with partial payment calculation.
- **Official Printable Fee Receipts** with timestamp, cashier signature line, and verification stamp.

### 7. 📢 Campus Notice Board
- Priority announcements (Urgent / Normal / Low).
- Target audience filtering: All School Community, Parents & Guardians, Teachers, or Pupils.

### 8. 🛡️ Enterprise-Grade Security & Access Control
- **CSRF Protection**: Cryptographic token generation (`secrets.token_hex(32)`) and validation on all POST requests to protect against Cross-Site Request Forgery.
- **Brute-Force Guard & Account Lockout**: Automatic rate-limiting that locks access for 15 minutes after 5 consecutive failed login attempts from any IP address.
- **Security Headers & Cookie Hardening**:
  - `X-Frame-Options: SAMEORIGIN` (prevents Clickjacking)
  - `X-Content-Type-Options: nosniff` (prevents MIME type sniffing)
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - Cookie flags: `HttpOnly` and `SameSite=Lax` with automatic session timeout.
- **Live Security Audit Trail**: Real-time logging of authentication events (`LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOCKED_OUT`, `USER_CREATED`, `PASSWORD_CHANGED`) with timestamps, IP tracking, and severity ratings directly visible in the Admin Control Center.
- **Password Strength Policy**: Enforces a minimum of 8 characters containing both letters and numbers for all staff accounts.
- **Role-Based Authority (RBAC)**: Enforced separation between `Admin` (full system control) and `Teacher` (academics & roll call).
- **Default Accounts**:
  - **Administrator**: `admin` / `admin123` (Full system control)
  - **Teacher**: `teacher` / `teacher123` (Academics & Attendance)

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+** (Python 3.15 installed on this environment)
- **Flask**:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Running the System
In this directory:
```bash
python app.py
```
Or double-click `run.bat` on Windows!

Open your browser to:
```
http://127.0.0.1:5000
```

*Note: The system automatically initializes the SQLite database (`school.db`) and pre-populates sample primary pupils, homeroom teachers, attendance records, grades, and notices on first launch!*

---

## 📁 Project Structure

```
primary_school_system/
├── app.py                  # Main Flask routes, controllers, and business logic
├── database.py             # SQLite database schemas, initialization & seed data
├── school.db               # SQLite database file (generated automatically)
├── requirements.txt        # Flask requirement
├── run.bat                 # 1-click Windows startup script
├── README.md               # System documentation & user guide
├── static/
│   ├── css/
│   │   └── custom.css      # Custom scrollbars, responsive and print stylesheets
│   └── js/
│       └── app.js          # Modal managers, shortcuts, and UI interactions
└── templates/
    ├── base.html           # Master navigation & layout with Lucide icons
    ├── dashboard.html      # High-level KPIs, attendance overview, capacity meters
    ├── students.html       # Pupils directory & enrollment modal
    ├── student_detail.html # Pupil profile, guardian contacts, allergies & grades
    ├── attendance.html     # Interactive roll call with "Mark All Present"
    ├── grades.html         # Evaluation grid & score recording
    ├── report_card.html    # Printable official primary school progress report
    ├── classes.html        # Homerooms & capacity tracking
    ├── teachers.html       # Faculty directory & homeroom allocations
    ├── fees.html           # Tuition invoices & payment modal
    ├── fee_receipt.html    # Printable payment receipt
    └── notices.html        # School notice board & circular publisher
```

