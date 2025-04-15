-- HostelMate Database Schema

-- Users table (common fields for all user types)
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(15),
    user_type ENUM('student', 'warden', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Student profiles
CREATE TABLE IF NOT EXISTS students (
    student_id INT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    roll_number VARCHAR(20) UNIQUE NOT NULL,
    department VARCHAR(50) NOT NULL,
    year_of_study INT NOT NULL,
    gender ENUM('male', 'female', 'other') NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Warden profiles
CREATE TABLE IF NOT EXISTS wardens (
    warden_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    department VARCHAR(50) NOT NULL,
    office_location VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Admin profiles
CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Hostel buildings
CREATE TABLE IF NOT EXISTS hostel_buildings (
    building_id INT AUTO_INCREMENT PRIMARY KEY,
    building_name VARCHAR(50) NOT NULL,
    gender_type ENUM('male', 'female', 'mixed') NOT NULL,
    total_rooms INT NOT NULL,
    address VARCHAR(255) NOT NULL,
    warden_id INT,
    FOREIGN KEY (warden_id) REFERENCES wardens(warden_id)
);

-- Rooms
CREATE TABLE IF NOT EXISTS rooms (
    room_id INT AUTO_INCREMENT PRIMARY KEY,
    building_id INT NOT NULL,
    room_number VARCHAR(10) NOT NULL,
    capacity INT NOT NULL DEFAULT 2,
    room_type ENUM('single', 'double', 'triple') NOT NULL,
    status ENUM('available', 'occupied', 'maintenance') NOT NULL DEFAULT 'available',
    floor_number INT NOT NULL,
    monthly_rent DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
    UNIQUE (building_id, room_number)
);

-- Room allocations
CREATE TABLE IF NOT EXISTS room_allocations (
    allocation_id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    student_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    status ENUM('active', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
    allocated_by INT NOT NULL,
    allocation_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (allocated_by) REFERENCES users(user_id)
);

-- Room applications
CREATE TABLE IF NOT EXISTS room_applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    preferred_building_id INT NOT NULL,
    preferred_room_type ENUM('single', 'double', 'triple') NOT NULL,
    preferred_floor INT,
    roommate_preference_id INT,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    processed_by INT,
    processed_date TIMESTAMP NULL,
    notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (preferred_building_id) REFERENCES hostel_buildings(building_id),
    FOREIGN KEY (roommate_preference_id) REFERENCES students(student_id),
    FOREIGN KEY (processed_by) REFERENCES users(user_id)
);

-- Complaints
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    room_id INT NOT NULL,
    complaint_type ENUM('plumbing', 'electrical', 'furniture', 'cleaning', 'wifi', 'other') NOT NULL,
    description TEXT NOT NULL,
    status ENUM('pending', 'in_progress', 'resolved', 'rejected') NOT NULL DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_date TIMESTAMP NULL,
    resolved_by INT,
    resolution_notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (resolved_by) REFERENCES users(user_id)
);

-- Mess schedules
CREATE TABLE IF NOT EXISTS mess_schedules (
    schedule_id INT AUTO_INCREMENT PRIMARY KEY,
    building_id INT NOT NULL,
    day_of_week ENUM('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday') NOT NULL,
    breakfast_menu TEXT NOT NULL,
    breakfast_time VARCHAR(20) NOT NULL,
    lunch_menu TEXT NOT NULL,
    lunch_time VARCHAR(20) NOT NULL,
    dinner_menu TEXT NOT NULL,
    dinner_time VARCHAR(20) NOT NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    UNIQUE (building_id, day_of_week)
);

-- Fee records
CREATE TABLE IF NOT EXISTS fee_records (
    fee_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    room_id INT NOT NULL,
    fee_type ENUM('room_rent', 'mess_fee', 'maintenance', 'other') NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    due_date DATE NOT NULL,
    payment_status ENUM('pending', 'paid', 'overdue') NOT NULL DEFAULT 'pending',
    payment_date TIMESTAMP NULL,
    payment_method ENUM('cash', 'card', 'bank_transfer', 'online') NULL,
    transaction_id VARCHAR(100) NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- Visitor records
CREATE TABLE IF NOT EXISTS visitor_records (
    visitor_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    visitor_name VARCHAR(100) NOT NULL,
    visitor_phone VARCHAR(15) NOT NULL,
    relation VARCHAR(50) NOT NULL,
    check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expected_check_out_time TIMESTAMP NOT NULL,
    actual_check_out_time TIMESTAMP NULL,
    purpose VARCHAR(255) NOT NULL,
    approved_by INT NOT NULL,
    status ENUM('checked_in', 'checked_out', 'overstayed') NOT NULL DEFAULT 'checked_in',
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (approved_by) REFERENCES users(user_id)
);

-- Hostel notices
CREATE TABLE IF NOT EXISTS hostel_notices (
    notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    image_url TEXT,
    building_id INTEGER NULL,
    posted_by INTEGER NOT NULL,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (building_id) REFERENCES hostel_buildings(building_id),
    FOREIGN KEY (posted_by) REFERENCES users(user_id)
);
