import os
import hashlib
from database_utils import get_db_connection, commit_db_changes, close_db_connection, is_postgres, adapt_query_for_db

def init_db():
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables
    print("Creating tables...")

    # Determine if we're using PostgreSQL
    postgres = is_postgres()

    # Users table
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone_number TEXT,
                user_type TEXT NOT NULL CHECK(user_type IN ('student', 'warden', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone_number TEXT,
                user_type TEXT NOT NULL CHECK(user_type IN ('student', 'warden', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # Students table
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                year_of_study INTEGER NOT NULL,
                gender TEXT NOT NULL CHECK(gender IN ('male', 'female', 'other')),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                year_of_study INTEGER NOT NULL,
                gender TEXT NOT NULL CHECK(gender IN ('male', 'female', 'other')),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')

    # Wardens table
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wardens (
                warden_id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                department TEXT NOT NULL,
                office_location TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wardens (
                warden_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                department TEXT NOT NULL,
                office_location TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')

    # Admins table
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                admin_id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                role TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                role TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')

    # Hostel buildings
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hostel_buildings (
                building_id SERIAL PRIMARY KEY,
                building_name TEXT NOT NULL,
                gender_type TEXT NOT NULL CHECK(gender_type IN ('male', 'female', 'mixed')),
                total_rooms INTEGER NOT NULL,
                address TEXT NOT NULL,
                warden_id INTEGER,
                location TEXT,
                gender TEXT,
                floors INTEGER,
                description TEXT,
                FOREIGN KEY (warden_id) REFERENCES wardens(warden_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hostel_buildings (
                building_id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_name TEXT NOT NULL,
                gender_type TEXT NOT NULL CHECK(gender_type IN ('male', 'female', 'mixed')),
                total_rooms INTEGER NOT NULL,
                address TEXT NOT NULL,
                warden_id INTEGER,
                location TEXT,
                gender TEXT,
                floors INTEGER,
                description TEXT,
                FOREIGN KEY (warden_id) REFERENCES wardens(warden_id)
            )
        ''')

    # Rooms
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id SERIAL PRIMARY KEY,
                building_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 2,
                room_type TEXT NOT NULL CHECK(room_type IN ('single', 'double', 'triple', 'quad')),
                status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'occupied', 'maintenance')),
                floor_number INTEGER NOT NULL,
                monthly_rent REAL NOT NULL,
                FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
                UNIQUE (building_id, room_number)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 2,
                room_type TEXT NOT NULL CHECK(room_type IN ('single', 'double', 'triple', 'quad')),
                status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'occupied', 'maintenance')),
                floor_number INTEGER NOT NULL,
                monthly_rent REAL NOT NULL,
                FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
                UNIQUE (building_id, room_number)
            )
        ''')

    # Room allocations
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_allocations (
                allocation_id SERIAL PRIMARY KEY,
                room_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                allocation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_allocations (
                allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                allocation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

    # Complaints
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                complaint_type TEXT NOT NULL CHECK(complaint_type IN ('plumbing', 'electrical', 'furniture', 'cleaning', 'wifi', 'other')),
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'resolved', 'rejected')),
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
                submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_date TIMESTAMP,
                resolved_by INTEGER,
                resolution_notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (resolved_by) REFERENCES users(user_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                complaint_type TEXT NOT NULL CHECK(complaint_type IN ('plumbing', 'electrical', 'furniture', 'cleaning', 'wifi', 'other')),
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'resolved', 'rejected')),
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
                submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_date TIMESTAMP,
                resolved_by INTEGER,
                resolution_notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (resolved_by) REFERENCES users(user_id)
            )
        ''')

    # Fee records
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fee_records (
                fee_id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                fee_type TEXT NOT NULL CHECK(fee_type IN ('room_rent', 'mess_fee', 'maintenance', 'other')),
                amount REAL NOT NULL,
                due_date DATE NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'pending' CHECK(payment_status IN ('pending', 'paid', 'overdue')),
                payment_date TIMESTAMP,
                payment_method TEXT CHECK(payment_method IN ('cash', 'card', 'bank_transfer', 'online')),
                transaction_id TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fee_records (
                fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                fee_type TEXT NOT NULL CHECK(fee_type IN ('room_rent', 'mess_fee', 'maintenance', 'other')),
                amount REAL NOT NULL,
                due_date DATE NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'pending' CHECK(payment_status IN ('pending', 'paid', 'overdue')),
                payment_date TIMESTAMP,
                payment_method TEXT CHECK(payment_method IN ('cash', 'card', 'bank_transfer', 'online')),
                transaction_id TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        ''')

    # Visitor records
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitor_records (
                visitor_id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                visitor_name TEXT NOT NULL,
                visitor_phone TEXT NOT NULL,
                relation TEXT NOT NULL,
                check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expected_check_out_time TIMESTAMP NOT NULL,
                actual_check_out_time TIMESTAMP,
                purpose TEXT NOT NULL,
                approved_by INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'checked_in' CHECK(status IN ('checked_in', 'checked_out', 'overstayed')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (approved_by) REFERENCES users(user_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitor_records (
                visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                visitor_name TEXT NOT NULL,
                visitor_phone TEXT NOT NULL,
                relation TEXT NOT NULL,
                check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expected_check_out_time TIMESTAMP NOT NULL,
                actual_check_out_time TIMESTAMP,
                purpose TEXT NOT NULL,
                approved_by INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'checked_in' CHECK(status IN ('checked_in', 'checked_out', 'overstayed')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (approved_by) REFERENCES users(user_id)
            )
        ''')

    # Hostel notices
    if postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hostel_notices (
                notice_id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                image_url TEXT,
                building_id INTEGER,
                posted_by INTEGER NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_date DATE,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
                FOREIGN KEY (posted_by) REFERENCES users(user_id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hostel_notices (
                notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                image_url TEXT,
                building_id INTEGER,
                posted_by INTEGER NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_date DATE,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
                FOREIGN KEY (posted_by) REFERENCES users(user_id)
            )
        ''')

    # Check if admin user exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    admin = cursor.fetchone()

    # Create default admin user if it doesn't exist
    if not admin:
        print("Creating default admin user...")
        # Hash the password
        password = "admin123"
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Insert admin user
        placeholder = '%s' if is_postgres() else '?'
        cursor.execute(
            f"INSERT INTO users (username, password, email, full_name, user_type) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) RETURNING user_id" if is_postgres() else
            f"INSERT INTO users (username, password, email, full_name, user_type) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
            ('admin', hashed_password, 'admin@hostelmate.com', 'Admin User', 'admin')
        )

        # Get the user_id
        if is_postgres():
            user_id = cursor.fetchone()[0]
        else:
            user_id = cursor.lastrowid

        # Insert admin profile
        cursor.execute(
            f"INSERT INTO admins (user_id, role) VALUES ({placeholder}, {placeholder})",
            (user_id, 'System Administrator')
        )

    # Commit changes
    conn.commit()
    print("Database initialized successfully!")

    # Close connection
    conn.close()

if __name__ == "__main__":
    init_db()
