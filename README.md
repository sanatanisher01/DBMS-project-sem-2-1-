# HostelMate

A comprehensive hostel management system that streamlines room allocation, complaint management, and fee tracking.

## Features

### Student Features
- Apply for rooms and roommate preferences
- Submit complaints (e.g., plumbing, electricity)
- View mess schedules and fees
- Access notices and announcements

### Warden (Faculty) Features
- Allocate/shift rooms
- Track and resolve maintenance requests
- Manage visitor records and hostel notices
- Monitor student occupancy

### Admin Features
- Oversee fee payment status
- Monitor complaint resolution statistics
- Generate room availability and occupancy reports
- Manage hostel buildings and rooms
- Upload notices with rich text formatting

## Technology Stack
- Frontend: HTML, CSS, JavaScript, Bootstrap
- Backend: Python with Flask
- Database: PostgreSQL (production) / SQLite (development)
- Image Storage: Cloudinary

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - **Name**: hostelmate (or your preferred name)
   - **Environment**: Python
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn app:app`
4. Add the following environment variables:
   - `SECRET_KEY`: A random string for session security
   - `CLOUDINARY_CLOUD_NAME`: Your Cloudinary cloud name
   - `CLOUDINARY_API_KEY`: Your Cloudinary API key
   - `CLOUDINARY_API_SECRET`: Your Cloudinary API secret
   - `DATABASE_URL`: Your PostgreSQL connection string (create a PostgreSQL database in Render first)
5. Deploy the application

## Local Development

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file with the required environment variables
6. Initialize the database: `python init_db.py`
7. Run the application: `python app.py`
8. Access the application at http://localhost:5000

## Default Admin Login

- Username: admin
- Password: admin123
