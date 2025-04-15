import os
import subprocess
import sys

def check_python_version():
    """Check if Python version is 3.6 or higher"""
    if sys.version_info < (3, 6):
        print("Error: Python 3.6 or higher is required.")
        sys.exit(1)
    print("Python version check passed.")

def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        'static/img',
        'static/uploads',
        'templates/student',
        'templates/warden',
        'templates/admin',
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def install_dependencies():
    """Install required packages from requirements.txt"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to install dependencies.")
        sys.exit(1)

def initialize_database():
    """Initialize the database"""
    try:
        subprocess.check_call([sys.executable, 'database/init_db.py'])
        print("Database initialized successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to initialize database.")
        sys.exit(1)

def main():
    """Main setup function"""
    print("Starting HostelMate setup...")
    
    check_python_version()
    create_directories()
    install_dependencies()
    
    # Ask user if they want to initialize the database
    init_db = input("Do you want to initialize the database? (y/n): ").lower()
    if init_db == 'y':
        initialize_database()
    
    print("\nSetup completed successfully!")
    print("\nTo run the application:")
    print("1. Make sure MySQL server is running")
    print("2. Run 'python app.py'")
    print("3. Access the application at http://localhost:5000")
    print("\nDefault login credentials:")
    print("Admin: username='admin', password='admin123'")
    print("Warden: username='warden', password='warden123'")
    print("Student: username='student', password='student123'")

if __name__ == "__main__":
    main()
