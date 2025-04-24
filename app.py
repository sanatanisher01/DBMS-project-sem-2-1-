from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import sqlite3
from functools import wraps
import os
import io
import base64
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import uuid
import hashlib
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Cloudinary configuration
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'dmkuayw2l'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '958734929781356'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'KV1aQjnZSvmV3zPoHFddoDdzV4k')
)

# Import database utility functions
from database_utils import get_db_connection, commit_db_changes, close_db_connection, is_postgres, adapt_query_for_db, get_placeholder

# User role decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Custom template context processor
@app.context_processor
def inject_template_context():
    context = {'user_type': session.get('user_type')}

    # Add pending visitor count for wardens
    if session.get('user_type') == 'warden' and session.get('user_id'):
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get warden's building
        query = adapt_query_for_db('''
            SELECT w.*, hb.building_id
            FROM wardens w
            LEFT JOIN hostel_buildings hb ON hb.warden_id = w.warden_id
            WHERE w.user_id = ?
        ''')
        cursor.execute(query, (session.get('user_id'),))
        warden = cursor.fetchone()

        if warden and warden['building_id']:
            # Count pending visitor approvals
            query = adapt_query_for_db('''
                SELECT COUNT(*) as count
                FROM visitor_records vr
                JOIN students s ON vr.student_id = s.student_id
                JOIN room_allocations ra ON s.student_id = ra.student_id
                JOIN rooms r ON ra.room_id = r.room_id
                WHERE r.building_id = ? AND vr.status = 'pending'
            ''')
            cursor.execute(query, (warden['building_id'],))
            result = cursor.fetchone()
            context['pending_visitor_count'] = result['count'] if result else 0

        cursor.close()
        conn.close()

    return context

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_type' not in session or session['user_type'] not in roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        query = adapt_query_for_db('SELECT * FROM users WHERE username = ?')
        print(f"Debug - Username: {username}")
        print(f"Debug - Query: {query}")
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        print(f"Debug - User found: {user is not None}")
        cursor.close()
        conn.close()

        if user:
            # Check if password is hashed with SHA-256 (from init_db.py)
            sha256_hashed = hashlib.sha256(password.encode()).hexdigest()

            print(f"Debug - Input password: {password}")
            print(f"Debug - SHA256 hash: {sha256_hashed}")
            print(f"Debug - Stored password hash: {user['password']}")

            # Try both methods of password verification
            if user['password'] == sha256_hashed or check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['user_type'] = user['user_type']

                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                print("Debug - Password verification failed")
                flash('Invalid username or password', 'error')
        else:
            print("Debug - User not found")
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_type = session['user_type']
    if user_type == 'student':
        return redirect(url_for('student_dashboard'))
    elif user_type == 'warden':
        return redirect(url_for('warden_dashboard'))
    elif user_type == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('index'))

# Student routes
@app.route('/student/dashboard')
@login_required
@role_required(['student'])
def student_dashboard():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student details
    query = adapt_query_for_db('''
        SELECT s.*, u.* FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    student = cursor.fetchone()

    # Get room allocation
    query = adapt_query_for_db('''
        SELECT ra.*, r.room_number, r.room_type, hb.building_name, hb.building_id
        FROM room_allocations ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE ra.student_id = ? AND ra.status = 'active'
    ''')
    cursor.execute(query, (student['student_id'],))
    room_allocation = cursor.fetchone()
    building_id = room_allocation['building_id'] if room_allocation else None

    # Get pending complaints
    query = adapt_query_for_db('''
        SELECT * FROM complaints
        WHERE student_id = ? AND status != 'resolved'
        ORDER BY submitted_date DESC
    ''')
    cursor.execute(query, (student['student_id'],))
    complaints = cursor.fetchall()

    # Get fee status
    query = adapt_query_for_db('''
        SELECT * FROM fee_records
        WHERE student_id = ?
        ORDER BY due_date DESC
    ''')
    cursor.execute(query, (student['student_id'],))
    fees = cursor.fetchall()

    # Get notices for the student's building or general notices
    if is_postgres():
        query = adapt_query_for_db('''
            SELECT hn.*, u.full_name as posted_by_name, hb.building_name
            FROM hostel_notices hn
            JOIN users u ON hn.posted_by = u.user_id
            LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
            WHERE hn.is_active = TRUE
            AND (hn.building_id IS NULL OR hn.building_id = %s)
            AND (hn.expiry_date IS NULL OR hn.expiry_date >= CURRENT_DATE)
            ORDER BY hn.posted_at DESC
            LIMIT 6
        ''')
        cursor.execute(query, (building_id,))
    else:
        query = adapt_query_for_db('''
            SELECT hn.*, u.full_name as posted_by_name, hb.building_name
            FROM hostel_notices hn
            JOIN users u ON hn.posted_by = u.user_id
            LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
            WHERE hn.is_active = 1
            AND (hn.building_id IS NULL OR hn.building_id = ?)
            AND (hn.expiry_date IS NULL OR hn.expiry_date >= date('now'))
            ORDER BY hn.posted_at DESC
            LIMIT 6
        ''')
        cursor.execute(query, (building_id,))
    notices = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('student/dashboard.html',
                          student=student,
                          room_allocation=room_allocation,
                          complaints=complaints,
                          fees=fees,
                          notices=notices)

@app.route('/student/apply-room', methods=['GET', 'POST'])
@login_required
@role_required(['student'])
def apply_room():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student details
    query = adapt_query_for_db('SELECT * FROM students WHERE user_id = ?')
    cursor.execute(query, (user_id,))
    student = cursor.fetchone()

    # Get hostel buildings
    query = adapt_query_for_db('''
        SELECT * FROM hostel_buildings
        WHERE gender_type = ? OR gender_type = 'mixed'
    ''')
    cursor.execute(query, (student['gender'],))
    buildings = cursor.fetchall()

    # Get potential roommates (same gender)
    query = adapt_query_for_db('''
        SELECT s.student_id, u.full_name, s.roll_number
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.gender = ? AND s.student_id != ?
    ''')
    cursor.execute(query, (student['gender'], student['student_id']))
    potential_roommates = cursor.fetchall()

    if request.method == 'POST':
        building_id = request.form['building_id']
        room_type = request.form['room_type']
        preferred_floor = request.form.get('preferred_floor')
        roommate_preference = request.form.get('roommate_preference')

        query = adapt_query_for_db('''
            INSERT INTO room_applications
            (student_id, preferred_building_id, preferred_room_type, preferred_floor, roommate_preference_id)
            VALUES (?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (
            student['student_id'],
            building_id,
            room_type,
            preferred_floor if preferred_floor else None,
            roommate_preference if roommate_preference else None
        ))

        conn.commit()
        flash('Room application submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    cursor.close()
    conn.close()

    return render_template('student/apply_room.html',
                          buildings=buildings,
                          potential_roommates=potential_roommates)

@app.route('/student/submit-complaint', methods=['GET', 'POST'])
@login_required
@role_required(['student'])
def submit_complaint():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student details
    query = adapt_query_for_db('SELECT * FROM students WHERE user_id = ?')
    cursor.execute(query, (user_id,))
    student = cursor.fetchone()

    # Get student's room
    query = adapt_query_for_db('''
        SELECT ra.*, r.*
        FROM room_allocations ra
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE ra.student_id = ? AND ra.status = 'active'
    ''')
    cursor.execute(query, (student['student_id'],))
    room = cursor.fetchone()

    if not room:
        flash('You must be allocated to a room to submit a complaint', 'error')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        complaint_type = request.form['complaint_type']
        description = request.form['description']
        priority = request.form['priority']

        query = adapt_query_for_db('''
            INSERT INTO complaints
            (student_id, room_id, complaint_type, description, priority)
            VALUES (?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (
            student['student_id'],
            room['room_id'],
            complaint_type,
            description,
            priority
        ))

        conn.commit()
        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    cursor.close()
    conn.close()

    return render_template('student/submit_complaint.html', room=room)

# Warden routes
@app.route('/warden/dashboard')
@login_required
@role_required(['warden'])
def warden_dashboard():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warden details
    query = adapt_query_for_db('''
        SELECT w.*, u.*, hb.building_id, hb.building_name
        FROM wardens w
        JOIN users u ON w.user_id = u.user_id
        LEFT JOIN hostel_buildings hb ON hb.warden_id = w.warden_id
        WHERE w.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    warden = cursor.fetchone()

    # Get pending room applications
    query = adapt_query_for_db('''
        SELECT ra.*, s.roll_number, u.full_name, hb.building_name
        FROM room_applications ra
        JOIN students s ON ra.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN hostel_buildings hb ON ra.preferred_building_id = hb.building_id
        WHERE hb.warden_id = ? AND ra.status = 'pending'
        ORDER BY ra.application_date ASC
    ''')
    cursor.execute(query, (warden['warden_id'],))
    applications = cursor.fetchall()

    # Get pending complaints
    query = adapt_query_for_db('''
        SELECT c.*, u.full_name, r.room_number, hb.building_name
        FROM complaints c
        JOIN students s ON c.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN rooms r ON c.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE hb.warden_id = ? AND c.status != 'resolved'
        ORDER BY c.priority DESC, c.submitted_date ASC
    ''')
    cursor.execute(query, (warden['warden_id'],))
    complaints = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('warden/dashboard.html',
                          warden=warden,
                          applications=applications,
                          complaints=complaints)

@app.route('/warden/allocate-room/<int:application_id>', methods=['GET', 'POST'])
@login_required
@role_required(['warden'])
def allocate_room(application_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get application details
    query = adapt_query_for_db('''
        SELECT ra.*, s.*, u.full_name, hb.building_name, hb.building_id
        FROM room_applications ra
        JOIN students s ON ra.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN hostel_buildings hb ON ra.preferred_building_id = hb.building_id
        WHERE ra.application_id = ?
    ''')
    cursor.execute(query, (application_id,))
    application = cursor.fetchone()

    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('warden_dashboard'))

    # Get available rooms
    query = adapt_query_for_db('''
        SELECT r.*
        FROM rooms r
        WHERE r.building_id = ?
        AND r.room_type = ?
        AND r.status = 'available'
        ORDER BY r.floor_number, r.room_number
    ''')
    cursor.execute(query, (application['building_id'], application['preferred_room_type']))
    available_rooms = cursor.fetchall()

    if request.method == 'POST':
        room_id = request.form['room_id']
        allocation_notes = request.form.get('allocation_notes', '')

        # Start a transaction
        conn.execute('BEGIN TRANSACTION')

        try:
            # Create room allocation
            query = adapt_query_for_db('''
                INSERT INTO room_allocations
                (room_id, student_id, start_date, allocated_by, allocation_notes)
                VALUES (?, ?, ?, ?, ?)
            ''')
            cursor.execute(query, (
                room_id,
                application['student_id'],
                datetime.date.today(),
                user_id,
                allocation_notes
            ))

            # Update room status
            query = adapt_query_for_db('''
                UPDATE rooms
                SET status = 'occupied'
                WHERE room_id = ?
            ''')
            cursor.execute(query, (room_id,))

            # Update application status
            query = adapt_query_for_db('''
                UPDATE room_applications
                SET status = 'approved', processed_by = ?, processed_date = CURRENT_TIMESTAMP
                WHERE application_id = ?
            ''')
            cursor.execute(query, (user_id, application_id))

            # Commit the transaction
            conn.commit()

            flash('Room allocated successfully!', 'success')
            return redirect(url_for('warden_dashboard'))

        except Exception as e:
            # Rollback in case of error
            conn.rollback()
            flash(f'Error allocating room: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return render_template('warden/allocate_room.html',
                          application=application,
                          available_rooms=available_rooms)

@app.route('/warden/manage-complaints')
@login_required
@role_required(['warden'])
def manage_complaints():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warden details
    query = adapt_query_for_db('''
        SELECT w.*, hb.building_id, hb.building_name
        FROM wardens w
        LEFT JOIN hostel_buildings hb ON hb.warden_id = w.warden_id
        WHERE w.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    warden = cursor.fetchone()

    if not warden or not warden['building_id']:
        flash('No building assigned to this warden', 'error')
        return redirect(url_for('warden_dashboard'))

    # Get all complaints for the warden's building
    query = adapt_query_for_db('''
        SELECT c.*, u.full_name, r.room_number, hb.building_name
        FROM complaints c
        JOIN students s ON c.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN rooms r ON c.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE hb.building_id = ?
        ORDER BY c.priority DESC, c.submitted_date ASC
    ''')
    cursor.execute(query, (warden['building_id'],))
    all_complaints = cursor.fetchall()

    # Separate complaints by priority and status
    high_priority_complaints = []
    medium_priority_complaints = []
    low_priority_complaints = []
    resolved_complaints = []

    for complaint in all_complaints:
        if complaint['status'] in ['resolved', 'rejected']:
            resolved_complaints.append(complaint)
        elif complaint['priority'] == 'high':
            high_priority_complaints.append(complaint)
        elif complaint['priority'] == 'medium':
            medium_priority_complaints.append(complaint)
        else:
            low_priority_complaints.append(complaint)

    cursor.close()
    conn.close()

    return render_template('warden/complaints.html',
                          high_priority_complaints=high_priority_complaints,
                          medium_priority_complaints=medium_priority_complaints,
                          low_priority_complaints=low_priority_complaints,
                          resolved_complaints=resolved_complaints)

@app.route('/warden/room-applications')
@login_required
@role_required(['warden'])
def room_applications():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warden details
    query = adapt_query_for_db('''
        SELECT w.*, hb.building_id, hb.building_name
        FROM wardens w
        LEFT JOIN hostel_buildings hb ON hb.warden_id = w.warden_id
        WHERE w.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    warden = cursor.fetchone()

    if not warden or not warden['building_id']:
        flash('No building assigned to this warden', 'error')
        return redirect(url_for('warden_dashboard'))

    # Get pending applications for the warden's building
    query = adapt_query_for_db('''
        SELECT ra.*, s.roll_number, u.full_name, hb.building_name
        FROM room_applications ra
        JOIN students s ON ra.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN hostel_buildings hb ON ra.preferred_building_id = hb.building_id
        WHERE hb.building_id = ? AND ra.status = 'pending'
        ORDER BY ra.application_date ASC
    ''')
    cursor.execute(query, (warden['building_id'],))
    applications = cursor.fetchall()

    # Get processed applications
    query = adapt_query_for_db('''
        SELECT ra.*, s.roll_number, u.full_name, hb.building_name,
               CASE WHEN ra.status = 'approved' THEN r.room_number ELSE NULL END as room_number
        FROM room_applications ra
        JOIN students s ON ra.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN hostel_buildings hb ON ra.preferred_building_id = hb.building_id
        LEFT JOIN room_allocations ral ON ra.student_id = ral.student_id AND ral.status = 'active'
        LEFT JOIN rooms r ON ral.room_id = r.room_id
        WHERE hb.building_id = ? AND ra.status != 'pending'
        ORDER BY ra.processed_date DESC
    ''')
    cursor.execute(query, (warden['building_id'],))
    processed_applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('warden/room_applications.html',
                          applications=applications,
                          processed_applications=processed_applications)

@app.route('/warden/resolve-complaint/<int:complaint_id>', methods=['GET', 'POST'])
@login_required
@role_required(['warden'])
def resolve_complaint(complaint_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get complaint details
    query = adapt_query_for_db('''
        SELECT c.*, u.full_name, r.room_number, hb.building_name
        FROM complaints c
        JOIN students s ON c.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN rooms r ON c.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE c.complaint_id = ?
    ''')
    cursor.execute(query, (complaint_id,))
    complaint = cursor.fetchone()

    if not complaint:
        flash('Complaint not found', 'error')
        return redirect(url_for('warden_dashboard'))

    if request.method == 'POST':
        status = request.form['status']
        resolution_notes = request.form['resolution_notes']

        query = adapt_query_for_db('''
            UPDATE complaints
            SET status = ?, resolution_notes = ?, resolved_by = ?, resolved_date = CURRENT_TIMESTAMP
            WHERE complaint_id = ?
        ''')
        cursor.execute(query, (status, resolution_notes, user_id, complaint_id))

        conn.commit()
        flash('Complaint updated successfully!', 'success')

        # Redirect to complaints page if coming from there
        if request.referrer and 'manage-complaints' in request.referrer:
            return redirect(url_for('manage_complaints'))
        return redirect(url_for('warden_dashboard'))

    cursor.close()
    conn.close()

    return render_template('warden/resolve_complaint.html', complaint=complaint)

# Admin routes
@app.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get occupancy statistics
    query = adapt_query_for_db('''
        SELECT hb.building_name,
               COUNT(r.room_id) AS total_rooms,
               SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_rooms,
               SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available_rooms,
               SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_rooms
        FROM hostel_buildings hb
        LEFT JOIN rooms r ON hb.building_id = r.building_id
        GROUP BY hb.building_id
    ''')
    cursor.execute(query)
    occupancy_stats = cursor.fetchall()

    # Get fee payment statistics
    query = adapt_query_for_db('''
        SELECT
            SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END) AS total_paid,
            SUM(CASE WHEN payment_status = 'pending' THEN amount ELSE 0 END) AS total_pending,
            SUM(CASE WHEN payment_status = 'overdue' THEN amount ELSE 0 END) AS total_overdue
        FROM fee_records
    ''')
    cursor.execute(query)
    fee_stats = cursor.fetchone()

    # Get complaint statistics
    if is_postgres():
        query = adapt_query_for_db('''
            SELECT
                COUNT(*) AS total_complaints,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_complaints,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_complaints,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved_complaints,
                COALESCE(AVG(CASE
                    WHEN status = 'resolved' AND resolved_date IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (resolved_date - submitted_date)) / 3600
                    ELSE NULL
                END), 0) AS avg_resolution_time_hours
            FROM complaints
        ''')
        cursor.execute(query)
    else:
        query = adapt_query_for_db('''
            SELECT
                COUNT(*) AS total_complaints,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_complaints,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_complaints,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved_complaints,
                COALESCE(AVG(CASE
                    WHEN status = 'resolved' AND resolved_date IS NOT NULL
                    THEN (julianday(resolved_date) - julianday(submitted_date)) * 24
                    ELSE NULL
                END), 0) AS avg_resolution_time_hours
            FROM complaints
        ''')
        cursor.execute(query)
    complaint_stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('admin/dashboard.html',
                          occupancy_stats=occupancy_stats,
                          fee_stats=fee_stats,
                          complaint_stats=complaint_stats)

@app.route('/admin/manage-users')
@login_required
@role_required(['admin'])
def manage_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('''
        SELECT u.*,
               CASE
                   WHEN u.user_type = 'student' THEN s.roll_number
                   WHEN u.user_type = 'warden' THEN w.department
                   ELSE a.role
               END AS additional_info
        FROM users u
        LEFT JOIN students s ON u.user_id = s.user_id AND u.user_type = 'student'
        LEFT JOIN wardens w ON u.user_id = w.user_id AND u.user_type = 'warden'
        LEFT JOIN admins a ON u.user_id = a.user_id AND u.user_type = 'admin'
        ORDER BY u.user_type, u.full_name
    ''')
    cursor.execute(query)
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/manage_users.html', users=users)

@app.route('/admin/add-user', methods=['POST'])
@login_required
@role_required(['admin'])
def add_user():
    try:
        # Get form data
        user_type = request.form.get('user_type')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        phone_number = request.form.get('phone_number')

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if username already exists
        query = adapt_query_for_db('SELECT * FROM users WHERE username = ?')
        cursor.execute(query, (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash('Username already exists. Please choose a different username.', 'error')
            return redirect(url_for('manage_users'))

        # Insert user into users table
        if is_postgres():
            query = adapt_query_for_db('''
                INSERT INTO users (username, password, email, full_name, user_type, phone_number)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id
            ''')
            cursor.execute(query, (username, hashed_password, email, full_name, user_type, phone_number))
            user_id = cursor.fetchone()[0]
        else:
            query = adapt_query_for_db('''
                INSERT INTO users (username, password, email, full_name, user_type, phone_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''')
            cursor.execute(query, (username, hashed_password, email, full_name, user_type, phone_number))
            user_id = cursor.lastrowid

        # Insert additional details based on user type
        if user_type == 'student':
            roll_number = request.form.get('roll_number')
            department = request.form.get('department')
            year_of_study = request.form.get('year_of_study')
            gender = request.form.get('gender')

            query = adapt_query_for_db('''
                INSERT INTO students (user_id, roll_number, department, year_of_study, gender)
                VALUES (?, ?, ?, ?, ?)
            ''')
            cursor.execute(query, (user_id, roll_number, department, year_of_study, gender))

        elif user_type == 'warden':
            department = request.form.get('warden_department')
            office_location = request.form.get('office_location')

            query = adapt_query_for_db('''
                INSERT INTO wardens (user_id, department, office_location)
                VALUES (?, ?, ?)
            ''')
            cursor.execute(query, (user_id, department, office_location))

        elif user_type == 'admin':
            role = request.form.get('admin_role')

            query = adapt_query_for_db('''
                INSERT INTO admins (user_id, role)
                VALUES (?, ?)
            ''')
            cursor.execute(query, (user_id, role))

        # Commit changes
        conn.commit()
        cursor.close()
        conn.close()

        flash('User added successfully!', 'success')
        return redirect(url_for('manage_users'))

    except Exception as e:
        flash(f'Error adding user: {str(e)}', 'error')
        return redirect(url_for('manage_users'))

@app.route('/admin/fee-reports')
@login_required
@role_required(['admin'])
def fee_reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('''
        SELECT fr.*, u.full_name, s.roll_number, r.room_number, hb.building_name
        FROM fee_records fr
        JOIN students s ON fr.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN rooms r ON fr.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        ORDER BY fr.due_date DESC
    ''')
    cursor.execute(query)
    fee_records = cursor.fetchall()

    # Get all students for the add fee form
    query = adapt_query_for_db('''
        SELECT s.student_id, s.roll_number, u.full_name
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        ORDER BY u.full_name
    ''')
    cursor.execute(query)
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/fee_reports.html', fee_records=fee_records, students=students)

@app.route('/warden/visitor-records', methods=['GET'])
@login_required
@role_required(['warden'])
def visitor_records():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warden details
    query = adapt_query_for_db('''
        SELECT w.*, hb.building_id
        FROM wardens w
        LEFT JOIN hostel_buildings hb ON hb.warden_id = w.warden_id
        WHERE w.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    warden = cursor.fetchone()

    # Get pending visitor approvals - using status instead of approval_status for compatibility
    query = adapt_query_for_db('''
        SELECT vr.*, u.full_name as student_name, r.room_number
        FROM visitor_records vr
        JOIN students s ON vr.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN room_allocations ra ON s.student_id = ra.student_id
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE r.building_id = ? AND vr.status = 'pending'
        ORDER BY vr.check_in_time DESC
    ''')
    cursor.execute(query, (warden['building_id'],))
    pending_visitors = cursor.fetchall()

    # Get all approved visitor records for the warden's building
    query = adapt_query_for_db('''
        SELECT vr.*, u.full_name as student_name, r.room_number,
               CASE WHEN vr.approved_by IS NOT NULL THEN wu.full_name ELSE NULL END as approved_by_name
        FROM visitor_records vr
        JOIN students s ON vr.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        LEFT JOIN users wu ON vr.approved_by = wu.user_id
        JOIN room_allocations ra ON s.student_id = ra.student_id
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE r.building_id = ? AND vr.status IN ('checked_in', 'checked_out', 'overstayed')
        ORDER BY vr.check_in_time DESC
    ''')
    cursor.execute(query, (warden['building_id'],))
    visitors = cursor.fetchall()

    # Get all students in the warden's building for the add visitor form
    query = adapt_query_for_db('''
        SELECT s.student_id, u.full_name, r.room_number
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        JOIN room_allocations ra ON s.student_id = ra.student_id
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE r.building_id = ? AND ra.end_date IS NULL
        ORDER BY u.full_name
    ''')
    cursor.execute(query, (warden['building_id'],))
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('warden/visitor_records.html',
                          visitors=visitors,
                          pending_visitors=pending_visitors,
                          students=students)

@app.route('/warden/add-visitor', methods=['POST'])
@login_required
@role_required(['warden'])
def add_visitor():
    user_id = session['user_id']

    student_id = request.form['student_id']
    visitor_name = request.form['visitor_name']
    visitor_phone = request.form['visitor_phone']
    relation = request.form['relation']
    purpose = request.form['purpose']
    expected_checkout = request.form['expected_checkout']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            INSERT INTO visitor_records
            (student_id, visitor_name, visitor_phone, relation, expected_check_out_time, purpose, approved_by, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (student_id, visitor_name, visitor_phone, relation, expected_checkout, purpose, user_id, 'checked_in'))

        conn.commit()
        flash('Visitor record added successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error adding visitor record: {e}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('visitor_records'))

@app.route('/warden/checkout-visitor/<int:visitor_id>', methods=['POST'])
@login_required
@role_required(['warden'])
def checkout_visitor(visitor_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            UPDATE visitor_records
            SET status = 'checked_out', actual_check_out_time = CURRENT_TIMESTAMP
            WHERE visitor_id = ?
        ''')
        cursor.execute(query, (visitor_id,))

        conn.commit()
        flash('Visitor checked out successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error checking out visitor: {e}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('visitor_records'))

@app.route('/warden/approve-visitor/<int:visitor_id>', methods=['POST'])
@login_required
@role_required(['warden'])
def approve_visitor(visitor_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            UPDATE visitor_records
            SET status = 'checked_in', approved_by = ?
            WHERE visitor_id = ?
        ''')
        cursor.execute(query, (user_id, visitor_id))

        conn.commit()
        flash('Visitor request approved successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error approving visitor: {e}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('visitor_records'))

@app.route('/warden/reject-visitor/<int:visitor_id>', methods=['POST'])
@login_required
@role_required(['warden'])
def reject_visitor(visitor_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            UPDATE visitor_records
            SET status = 'rejected', approved_by = ?
            WHERE visitor_id = ?
        ''')
        cursor.execute(query, (user_id, visitor_id))

        conn.commit()
        flash('Visitor request rejected!', 'success')
    except sqlite3.Error as e:
        flash(f'Error rejecting visitor: {e}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('visitor_records'))

@app.route('/warden/building-qr', methods=['GET'])
@login_required
@role_required(['warden'])
def building_qr():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warden's building
    query = adapt_query_for_db('''
        SELECT hb.*
        FROM hostel_buildings hb
        JOIN wardens w ON hb.warden_id = w.warden_id
        WHERE w.user_id = ?
    ''')
    cursor.execute(query, (user_id,))
    building = cursor.fetchone()

    cursor.close()
    conn.close()

    if not building:
        flash('No building assigned to this warden', 'error')
        return redirect(url_for('visitor_records'))

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    # URL for visitor registration with building ID
    registration_url = url_for('register_visitor_form', building_id=building['building_id'], _external=True)
    qr.add_data(registration_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert PIL image to base64 string
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    qr_code_url = f"data:image/png;base64,{img_str}"

    return render_template('warden/building_qr.html', building=building, qr_code_url=qr_code_url)

@app.route('/visitor-registration/<int:building_id>', methods=['GET'])
def register_visitor_form(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get building details
    query = adapt_query_for_db('SELECT * FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))
    building = cursor.fetchone()

    if not building:
        cursor.close()
        conn.close()
        return render_template('public/visitor_registration.html', building=None)

    # Get all students in the building
    query = adapt_query_for_db('''
        SELECT s.student_id, u.full_name, r.room_number
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        JOIN room_allocations ra ON s.student_id = ra.student_id
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE r.building_id = ? AND ra.end_date IS NULL
        ORDER BY u.full_name
    ''')
    cursor.execute(query, (building_id,))
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('public/visitor_registration.html', building=building, students=students)

@app.route('/register-visitor/<int:building_id>', methods=['POST'])
def register_visitor(building_id):
    # Validate building ID
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('SELECT * FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))
    building = cursor.fetchone()

    if not building:
        cursor.close()
        conn.close()
        flash('Invalid building ID. Please scan a valid QR code.', 'error')
        return redirect(url_for('index'))

    # Validate form data
    try:
        student_id = request.form['student_id']
        visitor_name = request.form['visitor_name']
        visitor_phone = request.form['visitor_phone']
        relation = request.form['relation']
        purpose = request.form['purpose']
        duration = int(request.form['duration'])

        # Validate student exists
        query = adapt_query_for_db('SELECT * FROM students WHERE student_id = ?')
        cursor.execute(query, (student_id,))
        student = cursor.fetchone()

        if not student:
            raise ValueError('Selected student does not exist')

        # Validate phone number format (basic check)
        if not visitor_phone.replace('-', '').replace('+', '').isdigit():
            raise ValueError('Phone number should contain only digits, hyphens, and plus sign')

        # Validate duration
        if duration not in [1, 2, 3, 4, 6, 8]:
            raise ValueError('Invalid duration selected')

    except KeyError as e:
        flash(f'Missing required field: {str(e)}', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('register_visitor_form', building_id=building_id))
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('register_visitor_form', building_id=building_id))

    # Calculate expected checkout time
    now = datetime.datetime.now()
    expected_checkout = now + datetime.timedelta(hours=duration)

    # Generate a unique hash for this visitor
    qr_code_hash = str(uuid.uuid4())

    try:
        query = adapt_query_for_db('''
            INSERT INTO visitor_records
            (student_id, visitor_name, visitor_phone, relation, expected_check_out_time, purpose, qr_code_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (student_id, visitor_name, visitor_phone, relation, expected_checkout, purpose, qr_code_hash, 'pending'))

        # Get the inserted visitor record
        visitor_id = cursor.lastrowid
        query = adapt_query_for_db('SELECT * FROM visitor_records WHERE visitor_id = ?')
        cursor.execute(query, (visitor_id,))
        visitor = cursor.fetchone()

        # Get student name
        query = adapt_query_for_db('''
            SELECT u.full_name
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.student_id = ?
        ''')
        cursor.execute(query, (student_id,))
        student_result = cursor.fetchone()
        student_name = student_result['full_name'] if student_result else 'Unknown'

        conn.commit()

        cursor.close()
        conn.close()

        # Redirect to success page with visitor details
        return render_template('public/registration_success.html',
                              visitor=visitor,
                              student_name=student_name,
                              duration=duration)

    except sqlite3.Error as e:
        flash(f'Error submitting visitor request: {e}', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('register_visitor_form', building_id=building_id))

# Notice Management Routes
@app.route('/admin/manage-notices')
@login_required
@role_required(['admin'])
def manage_notices():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all notices
    query = adapt_query_for_db('''
        SELECT hn.*, u.full_name as posted_by_name, hb.building_name
        FROM hostel_notices hn
        JOIN users u ON hn.posted_by = u.user_id
        LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
        ORDER BY hn.posted_at DESC
    ''')
    cursor.execute(query)
    notices = cursor.fetchall()

    # Get all buildings for the form
    query = adapt_query_for_db('SELECT * FROM hostel_buildings ORDER BY building_name')
    cursor.execute(query)
    buildings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/manage_notices.html', notices=notices, buildings=buildings)

@app.route('/admin/create-notice', methods=['POST'])
@login_required
@role_required(['admin'])
def create_notice():
    user_id = session['user_id']
    title = request.form['title']
    content = request.form['content']
    building_id = request.form.get('building_id') or None
    expiry_date = request.form.get('expiry_date') or None

    # Handle image upload
    image_url = None
    if 'notice_image' in request.files and request.files['notice_image'].filename:
        image_file = request.files['notice_image']
        try:
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result['secure_url']
        except Exception as e:
            flash(f'Error uploading image: {str(e)}', 'error')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            INSERT INTO hostel_notices
            (title, content, image_url, building_id, posted_by, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (title, content, image_url, building_id, user_id, expiry_date, True))

        conn.commit()
        flash('Notice published successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error publishing notice: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_notices'))

@app.route('/admin/view-notice/<int:notice_id>')
@login_required
@role_required(['admin'])
def view_notice(notice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('''
        SELECT hn.*, u.full_name as posted_by_name, hb.building_name
        FROM hostel_notices hn
        JOIN users u ON hn.posted_by = u.user_id
        LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
        WHERE hn.notice_id = ?
    ''')
    cursor.execute(query, (notice_id,))
    notice = cursor.fetchone()

    if not notice:
        flash('Notice not found', 'error')
        return redirect(url_for('manage_notices'))

    cursor.close()
    conn.close()

    return render_template('admin/view_notice.html', notice=notice)

@app.route('/admin/edit-notice/<int:notice_id>')
@login_required
@role_required(['admin'])
def edit_notice(notice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('''
        SELECT hn.*, u.full_name as posted_by_name, hb.building_name
        FROM hostel_notices hn
        JOIN users u ON hn.posted_by = u.user_id
        LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
        WHERE hn.notice_id = ?
    ''')
    cursor.execute(query, (notice_id,))
    notice = cursor.fetchone()

    if not notice:
        flash('Notice not found', 'error')
        return redirect(url_for('manage_notices'))

    # Get all buildings for the form
    query = adapt_query_for_db('SELECT * FROM hostel_buildings ORDER BY building_name')
    cursor.execute(query)
    buildings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/edit_notice.html', notice=notice, buildings=buildings)

@app.route('/admin/update-notice/<int:notice_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def update_notice(notice_id):
    title = request.form['title']
    content = request.form['content']
    building_id = request.form.get('building_id') or None
    expiry_date = request.form.get('expiry_date') or None
    remove_image = 'remove_image' in request.form

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current notice
    query = adapt_query_for_db('SELECT * FROM hostel_notices WHERE notice_id = ?')
    cursor.execute(query, (notice_id,))
    notice = cursor.fetchone()

    if not notice:
        flash('Notice not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_notices'))

    # Handle image upload or removal
    image_url = notice['image_url']
    if remove_image:
        image_url = None
    elif 'notice_image' in request.files and request.files['notice_image'].filename:
        image_file = request.files['notice_image']
        try:
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result['secure_url']
        except Exception as e:
            flash(f'Error uploading image: {str(e)}', 'error')

    try:
        query = adapt_query_for_db('''
            UPDATE hostel_notices
            SET title = ?, content = ?, image_url = ?, building_id = ?, expiry_date = ?
            WHERE notice_id = ?
        ''')
    cursor.execute(query, (title, content, image_url, building_id, expiry_date, notice_id))

        conn.commit()
        flash('Notice updated successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error updating notice: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('view_notice', notice_id=notice_id))

@app.route('/admin/toggle-notice/<int:notice_id>')
@login_required
@role_required(['admin'])
def toggle_notice(notice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current notice status
    query = adapt_query_for_db('SELECT is_active FROM hostel_notices WHERE notice_id = ?')
    cursor.execute(query, (notice_id,))
    notice = cursor.fetchone()

    if not notice:
        flash('Notice not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_notices'))

    # Toggle status
    new_status = not notice['is_active']

    try:
        query = adapt_query_for_db('UPDATE hostel_notices SET is_active = ? WHERE notice_id = ?')
        cursor.execute(query, (new_status, notice_id))
        conn.commit()
        status_text = 'activated' if new_status else 'deactivated'
        flash(f'Notice {status_text} successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error updating notice: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_notices'))

# Student notice routes
@app.route('/student/view-notice/<int:notice_id>')
@login_required
@role_required(['student'])
def view_student_notice(notice_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student details
    query = adapt_query_for_db('SELECT * FROM students WHERE user_id = ?')
    cursor.execute(query, (user_id,))
    student = cursor.fetchone()

    # Get student's building
    query = adapt_query_for_db('''
        SELECT hb.building_id
        FROM room_allocations ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE ra.student_id = ? AND ra.status = 'active'
    ''')
    cursor.execute(query, (student['student_id'],))
    building_result = cursor.fetchone()
    building_id = building_result['building_id'] if building_result else None

    # Get the notice, ensuring it's either for all buildings or for the student's building
    query = adapt_query_for_db('''
        SELECT hn.*, u.full_name as posted_by_name, hb.building_name
        FROM hostel_notices hn
        JOIN users u ON hn.posted_by = u.user_id
        LEFT JOIN hostel_buildings hb ON hn.building_id = hb.building_id
        WHERE hn.notice_id = ? AND hn.is_active = 1
        AND (hn.building_id IS NULL OR hn.building_id = ?)
    ''')
    cursor.execute(query, (notice_id, building_id))
    notice = cursor.fetchone()

    if not notice:
        flash('Notice not found or not available for your hostel', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('student_dashboard'))

    cursor.close()
    conn.close()

    return render_template('student/view_notice.html', notice=notice)

# Student dashboard route is already defined above

# Occupancy Reports
@app.route('/admin/occupancy-reports')
@login_required
@role_required(['admin'])
def occupancy_reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get occupancy statistics by building
    query = adapt_query_for_db('''
        SELECT hb.building_name,
               COUNT(r.room_id) AS total_rooms,
               SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_rooms,
               SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available_rooms,
               SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_rooms
        FROM hostel_buildings hb
        LEFT JOIN rooms r ON hb.building_id = r.building_id
        GROUP BY hb.building_id
        ORDER BY hb.building_name
    ''')
    cursor.execute(query)
    occupancy_stats_data = cursor.fetchall()

    # Convert SQLite Row objects to dictionaries
    occupancy_stats = [dict(stat) for stat in occupancy_stats_data]

    # Get total occupancy statistics
    query = adapt_query_for_db('''
        SELECT COUNT(r.room_id) AS total_rooms,
               SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_rooms,
               SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available_rooms,
               SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_rooms
        FROM rooms r
    ''')
    cursor.execute(query)
    total_stats_data = cursor.fetchone()

    # Convert to dictionary or create default values
    if not total_stats_data or total_stats_data['total_rooms'] is None:
        total_stats = {
            'total_rooms': 0,
            'occupied_rooms': 0,
            'available_rooms': 0,
            'maintenance_rooms': 0
        }
    else:
        total_stats = dict(total_stats_data)

    # Calculate overall occupancy rate
    overall_occupancy_rate = 0
    if total_stats['total_rooms'] > 0:
        overall_occupancy_rate = round((total_stats['occupied_rooms'] / total_stats['total_rooms']) * 100)

    # Get room type statistics
    query = adapt_query_for_db('''
        SELECT r.room_type,
               COUNT(r.room_id) AS total,
               SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied,
               SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available,
               SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance
        FROM rooms r
        GROUP BY r.room_type
    ''')
    cursor.execute(query)
    room_type_results = cursor.fetchall()

    # Convert to dictionary for easier template access
    room_type_stats = {}
    for result in room_type_results:
        result_dict = dict(result)
        room_type_stats[result_dict['room_type']] = {
            'total': result_dict['total'],
            'occupied': result_dict['occupied'],
            'available': result_dict['available'],
            'maintenance': result_dict['maintenance']
        }

    cursor.close()
    conn.close()

    return render_template('admin/occupancy_reports.html',
                          occupancy_stats=occupancy_stats,
                          total_stats=total_stats,
                          overall_occupancy_rate=overall_occupancy_rate,
                          room_type_stats=room_type_stats)

# Manage Hostel Buildings
@app.route('/admin/manage-hostels')
@login_required
@role_required(['admin'])
def manage_hostels():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all hostel buildings with occupancy statistics
    query = adapt_query_for_db('''
        SELECT hb.*,
               COUNT(r.room_id) AS total_rooms,
               SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_rooms,
               SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available_rooms,
               SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_rooms
        FROM hostel_buildings hb
        LEFT JOIN rooms r ON hb.building_id = r.building_id
        GROUP BY hb.building_id
        ORDER BY hb.building_name
    ''')
    cursor.execute(query)
    buildings_data = cursor.fetchall()

    # Convert SQLite Row objects to dictionaries
    buildings = []
    for building_data in buildings_data:
        # Convert SQLite Row to dict
        building = dict(building_data)

        # Handle NULL values for buildings with no rooms
        if building['total_rooms'] is None:
            building['total_rooms'] = 0
            building['occupied_rooms'] = 0
            building['available_rooms'] = 0
            building['maintenance_rooms'] = 0

        buildings.append(building)

    cursor.close()
    conn.close()

    return render_template('admin/manage_hostels.html', buildings=buildings)

@app.route('/admin/add-hostel-building', methods=['POST'])
@login_required
@role_required(['admin'])
def add_hostel_building():
    building_name = request.form['building_name']
    location = request.form['location']
    gender = request.form['gender']
    floors = int(request.form['floors'])
    description = request.form.get('description', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            INSERT INTO hostel_buildings
            (building_name, location, gender, floors, description, gender_type, total_rooms, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''')
        cursor.execute(query, (building_name, location, gender, floors, description, gender, 0, location))

        conn.commit()
        flash('Hostel building added successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error adding hostel building: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_hostels'))

@app.route('/admin/edit-hostel-building/<int:building_id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def edit_hostel_building(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        building_name = request.form['building_name']
        location = request.form['location']
        gender = request.form['gender']
        floors = int(request.form['floors'])
        description = request.form.get('description', '')

        try:
            query = adapt_query_for_db('''
                UPDATE hostel_buildings
                SET building_name = ?, location = ?, gender = ?, floors = ?, description = ?, gender_type = ?, address = ?
                WHERE building_id = ?
            ''')
            cursor.execute(query, (building_name, location, gender, floors, description, gender, location, building_id))

            conn.commit()
            flash('Hostel building updated successfully!', 'success')
            return redirect(url_for('manage_hostels'))
        except sqlite3.Error as e:
            flash(f'Error updating hostel building: {str(e)}', 'error')

    # Get building details
    query = adapt_query_for_db('SELECT * FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))
    building_data = cursor.fetchone()

    if not building_data:
        flash('Hostel building not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    # Convert SQLite Row to dict
    building = dict(building_data)

    cursor.close()
    conn.close()

    return render_template('admin/edit_hostel_building.html', building=building)

@app.route('/admin/delete-hostel-building/<int:building_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_hostel_building(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First, delete all room allocations for rooms in this building
        query = adapt_query_for_db('''
            DELETE FROM room_allocations
            WHERE room_id IN (SELECT room_id FROM rooms WHERE building_id = ?)
        ''')
    cursor.execute(query, (building_id,))

        # Then, delete all rooms in this building
        query = adapt_query_for_db('DELETE FROM rooms WHERE building_id = ?')
    cursor.execute(query, (building_id,))

        # Finally, delete the building itself
        query = adapt_query_for_db('DELETE FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))

        conn.commit()
        flash('Hostel building and all associated rooms deleted successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error deleting hostel building: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_hostels'))

# Manage Rooms
@app.route('/admin/manage-rooms/<int:building_id>')
@login_required
@role_required(['admin'])
def manage_rooms(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get building details
    query = adapt_query_for_db('SELECT * FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))
    building = cursor.fetchone()

    if not building:
        flash('Hostel building not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    # Get all rooms in the building
    query = adapt_query_for_db('''
        SELECT * FROM rooms
        WHERE building_id = ?
        ORDER BY floor_number, room_number
    ''')
    cursor.execute(query, (building_id,))
    rooms_data = cursor.fetchall()

    # Convert SQLite Row objects to dictionaries
    rooms = []
    for room_data in rooms_data:
        # Convert SQLite Row to dict
        room = dict(room_data)

        # Get occupants for this room
        query = adapt_query_for_db('''
            SELECT s.student_id, s.roll_number, u.full_name
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.student_id
            JOIN users u ON s.user_id = u.user_id
            WHERE ra.room_id = ? AND ra.status = 'active'
        ''')
    cursor.execute(query, (room['room_id'],))
        room['occupants'] = cursor.fetchall()

        # Set capacity based on room type
        if room['room_type'] == 'single':
            room['capacity'] = 1
        elif room['room_type'] == 'double':
            room['capacity'] = 2
        elif room['room_type'] == 'triple':
            room['capacity'] = 3
        elif room['room_type'] == 'quad':
            room['capacity'] = 4
        else:
            room['capacity'] = 1

        rooms.append(room)

    # Get available students (not allocated to any room)
    query = adapt_query_for_db('''
        SELECT s.student_id, s.roll_number, u.full_name
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.student_id NOT IN (
            SELECT student_id FROM room_allocations WHERE status = 'active')
    cursor.execute(query)
        AND s.gender = ?
        ORDER BY u.full_name
    ''', (building['gender'],))
    available_students = cursor.fetchall()

    # Convert building SQLite Row to dict
    building_dict = dict(building)

    cursor.close()
    conn.close()

    return render_template('admin/manage_rooms.html',
                          building=building_dict,
                          rooms=rooms,
                          available_students=available_students)

@app.route('/admin/add-rooms/<int:building_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def add_rooms(building_id):
    floor = int(request.form['floor'])
    room_type = request.form['room_type']
    start_number = request.form['start_number']
    count = int(request.form['count'])
    monthly_rent = float(request.form['monthly_rent'])

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if building exists
    query = adapt_query_for_db('SELECT * FROM hostel_buildings WHERE building_id = ?')
    cursor.execute(query, (building_id,))
    building = cursor.fetchone()

    if not building:
        flash('Hostel building not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    # Generate room numbers
    try:
        # If start_number is numeric, increment it
        if start_number.isdigit():
            for i in range(count):
                room_number = str(int(start_number) + i)
                query = adapt_query_for_db('''
                    INSERT INTO rooms
                    (building_id, room_number, floor_number, room_type, status, monthly_rent)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''')
    cursor.execute(query, (building_id, room_number, floor, room_type, 'available', monthly_rent))
        else:
            # If start_number has a prefix (e.g., A101), extract the numeric part and increment it
            prefix = ''.join([c for c in start_number if not c.isdigit()])
            numeric_part = ''.join([c for c in start_number if c.isdigit()])

            if numeric_part:
                for i in range(count):
                    room_number = prefix + str(int(numeric_part) + i)
                    query = adapt_query_for_db('''
                        INSERT INTO rooms
                        (building_id, room_number, floor_number, room_type, status, monthly_rent)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''')
    cursor.execute(query, (building_id, room_number, floor, room_type, 'available', monthly_rent))
            else:
                flash('Invalid room number format', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('manage_rooms', building_id=building_id))

        conn.commit()
        flash(f'{count} rooms added successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error adding rooms: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_rooms', building_id=building_id))

@app.route('/admin/update-room/<int:room_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def update_room(room_id):
    room_number = request.form['room_number']
    floor = int(request.form['floor'])
    room_type = request.form['room_type']
    monthly_rent = float(request.form['monthly_rent'])
    status = request.form['status']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get room details to get building_id
    query = adapt_query_for_db('SELECT building_id FROM rooms WHERE room_id = ?')
    cursor.execute(query, (room_id,))
    room = cursor.fetchone()

    if not room:
        flash('Room not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    building_id = room['building_id']

    try:
        query = adapt_query_for_db('''
            UPDATE rooms
            SET room_number = ?, floor_number = ?, room_type = ?, monthly_rent = ?, status = ?
            WHERE room_id = ?
        ''')
    cursor.execute(query, (room_number, floor, room_type, monthly_rent, status, room_id))

        conn.commit()
        flash('Room updated successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error updating room: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_rooms', building_id=building_id))

@app.route('/admin/delete-room/<int:room_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_room(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get room details to get building_id
    query = adapt_query_for_db('SELECT building_id FROM rooms WHERE room_id = ?')
    cursor.execute(query, (room_id,))
    room = cursor.fetchone()

    if not room:
        flash('Room not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    building_id = room['building_id']

    try:
        # First, delete all room allocations for this room
        query = adapt_query_for_db('DELETE FROM room_allocations WHERE room_id = ?')
    cursor.execute(query, (room_id,))

        # Then, delete the room itself
        query = adapt_query_for_db('DELETE FROM rooms WHERE room_id = ?')
    cursor.execute(query, (room_id,))

        conn.commit()
        flash('Room and all allocations deleted successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error deleting room: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_rooms', building_id=building_id))

@app.route('/admin/add-student-to-room/<int:room_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def add_student_to_room(room_id):
    student_id = request.form['student_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get room details
    query = adapt_query_for_db('''
        SELECT r.*, hb.gender
        FROM rooms r
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE r.room_id = ?
    ''')
    cursor.execute(query, (room_id,))
    room = cursor.fetchone()

    if not room:
        flash('Room not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    # Check if room is available
    if room['status'] == 'maintenance':
        flash('Cannot allocate a room that is under maintenance', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_rooms', building_id=room['building_id']))

    # Check if student exists and gender matches
    query = adapt_query_for_db('''
        SELECT s.*
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.student_id = ?
    ''')
    cursor.execute(query, (student_id,))
    student = cursor.fetchone()

    if not student:
        flash('Student not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_rooms', building_id=room['building_id']))

    if student['gender'] != room['gender']:
        flash('Student gender does not match hostel gender', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_rooms', building_id=room['building_id']))

    # Check if student is already allocated to a room
    query = adapt_query_for_db('''
        SELECT * FROM room_allocations
        WHERE student_id = ? AND status = 'active'
    ''')
    cursor.execute(query, (student_id,))
    existing_allocation = cursor.fetchone()

    if existing_allocation:
        flash('Student is already allocated to a room', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_rooms', building_id=room['building_id']))

    # Check if room is full
    query = adapt_query_for_db('''
        SELECT COUNT(*) as current_occupants
        FROM room_allocations
        WHERE room_id = ? AND status = 'active'
    ''')
    cursor.execute(query, (room_id,))
    occupancy = cursor.fetchone()

    capacity = 1
    if room['room_type'] == 'single':
        capacity = 1
    elif room['room_type'] == 'double':
        capacity = 2
    elif room['room_type'] == 'triple':
        capacity = 3
    elif room['room_type'] == 'quad':
        capacity = 4

    if occupancy['current_occupants'] >= capacity:
        flash('Room is already at full capacity', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_rooms', building_id=room['building_id']))

    try:
        # Add student to room
        query = adapt_query_for_db('''
            INSERT INTO room_allocations
            (student_id, room_id, allocation_date, status)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'active')
    cursor.execute(query)
        ''', (student_id, room_id))

        # Update room status to occupied
        query = adapt_query_for_db('''
            UPDATE rooms
            SET status = 'occupied'
            WHERE room_id = ?
        ''')
    cursor.execute(query, (room_id,))

        conn.commit()
        flash('Student allocated to room successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error allocating room: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_rooms', building_id=room['building_id']))

@app.route('/admin/remove-student-from-room/<int:room_id>/<int:student_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def remove_student_from_room(room_id, student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get room details
    query = adapt_query_for_db('SELECT building_id FROM rooms WHERE room_id = ?')
    cursor.execute(query, (room_id,))
    room = cursor.fetchone()

    if not room:
        flash('Room not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('manage_hostels'))

    try:
        # Update allocation status
        query = adapt_query_for_db('''
            UPDATE room_allocations
            SET status = 'inactive', end_date = CURRENT_TIMESTAMP
            WHERE room_id = ? AND student_id = ? AND status = 'active'
        ''')
    cursor.execute(query, (room_id, student_id))

        # Check if there are any remaining active allocations for this room
        query = adapt_query_for_db('''
            SELECT COUNT(*) as remaining_occupants
            FROM room_allocations
            WHERE room_id = ? AND status = 'active'
        ''')
    cursor.execute(query, (room_id,))
        remaining = cursor.fetchone()

        # If no remaining occupants, update room status to available
        if remaining['remaining_occupants'] == 0:
            query = adapt_query_for_db('''
                UPDATE rooms
                SET status = 'available'
                WHERE room_id = ?
            ''')
    cursor.execute(query, (room_id,))

        conn.commit()
        flash('Student removed from room successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error removing student from room: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('manage_rooms', building_id=room['building_id']))

# Fix admin fee section
@app.route('/admin/add-fee-record', methods=['POST'])
@login_required
@role_required(['admin'])
def add_fee_record():
    user_id = session['user_id']
    student_id = request.form['student_id']
    room_id = request.form['room_id']
    fee_type = request.form['fee_type']
    amount = float(request.form['amount'])
    due_date = request.form['due_date']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            INSERT INTO fee_records
            (student_id, room_id, fee_type, amount, due_date, payment_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''')
    cursor.execute(query, (student_id, room_id, fee_type, amount, due_date, 'pending', user_id))

        conn.commit()
        flash('Fee record added successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error adding fee record: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('fee_reports'))

@app.route('/admin/mark-fee-paid/<int:fee_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def mark_fee_paid(fee_id):
    payment_method = request.form['payment_method']
    transaction_id = request.form.get('transaction_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = adapt_query_for_db('''
            UPDATE fee_records
            SET payment_status = 'paid', payment_date = CURRENT_TIMESTAMP,
                payment_method = ?, transaction_id = ?
            WHERE fee_id = ?
        ''')
    cursor.execute(query, (payment_method, transaction_id, fee_id))

        conn.commit()
        flash('Fee marked as paid successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error updating fee record: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return redirect(url_for('fee_reports'))

@app.route('/admin/get-student-rooms/<int:student_id>')
@login_required
@role_required(['admin'])
def get_student_rooms(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = adapt_query_for_db('''
        SELECT r.room_id, r.room_number, hb.building_name
        FROM room_allocations ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN hostel_buildings hb ON r.building_id = hb.building_id
        WHERE ra.student_id = ? AND ra.status = 'active'
    ''')
    cursor.execute(query, (student_id,))
    rooms = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([dict(room) for room in rooms])

if __name__ == '__main__':
    # Get port from environment variable or use 5000 as default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
