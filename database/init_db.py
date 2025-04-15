import sqlite3
import os
from werkzeug.security import generate_password_hash
import datetime

# Database file path
DB_PATH = 'database/hostelmate.db'

def create_database():
    """Create the database if it doesn't exist"""
    # SQLite creates the database file automatically if it doesn't exist
    # when we connect to it
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Existing database removed.")

    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Connect to create the database file
    conn = sqlite3.connect(DB_PATH)
    conn.close()
    print(f"Database created at {DB_PATH}.")

def create_tables():
    """Create tables for SQLite"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create users table
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

        # Create students table
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

        # Create wardens table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wardens (
            warden_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            department TEXT NOT NULL,
            office_location TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        ''')

        # Create admins table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            role TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        ''')

        # Create hostel_buildings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hostel_buildings (
            building_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            gender_type TEXT NOT NULL CHECK(gender_type IN ('male', 'female', 'mixed')),
            total_rooms INTEGER NOT NULL,
            address TEXT NOT NULL,
            warden_id INTEGER,
            FOREIGN KEY (warden_id) REFERENCES wardens(warden_id)
        )
        ''')

        # Create rooms table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 2,
            room_type TEXT NOT NULL CHECK(room_type IN ('single', 'double', 'triple')),
            status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'occupied', 'maintenance')),
            floor_number INTEGER NOT NULL,
            monthly_rent REAL NOT NULL,
            FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
            UNIQUE (building_id, room_number)
        )
        ''')

        # Create room_allocations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled')),
            allocated_by INTEGER NOT NULL,
            allocation_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (allocated_by) REFERENCES users(user_id)
        )
        ''')

        # Create room_applications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            preferred_building_id INTEGER NOT NULL,
            preferred_room_type TEXT NOT NULL CHECK(preferred_room_type IN ('single', 'double', 'triple')),
            preferred_floor INTEGER,
            roommate_preference_id INTEGER,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            processed_by INTEGER,
            processed_date TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (preferred_building_id) REFERENCES hostel_buildings(building_id),
            FOREIGN KEY (roommate_preference_id) REFERENCES students(student_id),
            FOREIGN KEY (processed_by) REFERENCES users(user_id)
        )
        ''')

        # Create complaints table
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

        # Create mess_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mess_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL CHECK(day_of_week IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')),
            breakfast_menu TEXT NOT NULL,
            breakfast_time TEXT NOT NULL,
            lunch_menu TEXT NOT NULL,
            lunch_time TEXT NOT NULL,
            dinner_menu TEXT NOT NULL,
            dinner_time TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
            FOREIGN KEY (created_by) REFERENCES users(user_id),
            UNIQUE (building_id, day_of_week)
        )
        ''')

        # Create fee_records table
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

        # Create visitor_records table
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
            approved_by INTEGER,
            approval_status TEXT NOT NULL DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'checked_in', 'checked_out', 'overstayed')),
            qr_code_hash TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (approved_by) REFERENCES users(user_id)
        )
        ''')

        # Create hostel_notices table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hostel_notices (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            building_id INTEGER,
            posted_by INTEGER NOT NULL,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date DATE,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
            FOREIGN KEY (posted_by) REFERENCES users(user_id)
        )
        ''')

        conn.commit()
        print("Tables created successfully.")
    except sqlite3.Error as err:
        print(f"Error creating tables: {err}")
    finally:
        cursor.close()
        conn.close()

def insert_sample_data():
    """Insert sample data for testing"""
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Insert admin user
        cursor.execute('''
            INSERT INTO users (username, password, email, full_name, phone_number, user_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'admin',
            generate_password_hash('admin123'),
            'admin@hostelmate.com',
            'Admin User',
            '9876543210',
            'admin'
        ))
        admin_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO admins (user_id, role)
            VALUES (?, ?)
        ''', (admin_id, 'System Administrator'))

        # Insert warden user
        cursor.execute('''
            INSERT INTO users (username, password, email, full_name, phone_number, user_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'warden',
            generate_password_hash('warden123'),
            'warden@hostelmate.com',
            'Warden User',
            '9876543211',
            'warden'
        ))
        warden_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO wardens (user_id, department, office_location)
            VALUES (?, ?, ?)
        ''', (warden_id, 'Computer Science', 'Block A, Room 101'))
        warden_profile_id = cursor.lastrowid

        # Insert student user
        cursor.execute('''
            INSERT INTO users (username, password, email, full_name, phone_number, user_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'student',
            generate_password_hash('student123'),
            'student@hostelmate.com',
            'Student User',
            '9876543212',
            'student'
        ))
        student_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO students (user_id, roll_number, department, year_of_study, gender)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, 'CS2023001', 'Computer Science', 2, 'male'))
        student_profile_id = cursor.lastrowid

        # Insert hostel building
        cursor.execute('''
            INSERT INTO hostel_buildings (building_name, gender_type, total_rooms, address, warden_id)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Boys Hostel', 'male', 100, 'University Campus, Block B', warden_profile_id))
        building_id = cursor.lastrowid

        # Insert rooms
        for i in range(1, 11):
            cursor.execute('''
                INSERT INTO rooms (building_id, room_number, capacity, room_type, floor_number, monthly_rent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (building_id, f'B{i:03d}', 2, 'double', 1, 5000.00))

        # Insert room application
        cursor.execute('''
            INSERT INTO room_applications (student_id, preferred_building_id, preferred_room_type, application_date)
            VALUES (?, ?, ?, ?)
        ''', (student_profile_id, building_id, 'double', datetime.datetime.now()))

        # Get the first room ID
        cursor.execute('SELECT room_id FROM rooms LIMIT 1')
        room_id = cursor.fetchone()[0]

        # Insert complaint
        cursor.execute('''
            INSERT INTO complaints (student_id, room_id, complaint_type, description, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_profile_id, room_id, 'plumbing', 'Water leakage in bathroom', 'high'))

        # Insert fee record
        cursor.execute('''
            INSERT INTO fee_records (student_id, room_id, fee_type, amount, due_date, payment_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_profile_id, room_id, 'room_rent', 5000.00, datetime.date.today() + datetime.timedelta(days=30), 'pending', admin_id))

        conn.commit()
        print("Sample data inserted successfully.")
    except sqlite3.Error as err:
        print(f"Error inserting sample data: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("Initializing HostelMate database...")
    create_database()
    create_tables()
    insert_sample_data()
    print("Database initialization complete!")
