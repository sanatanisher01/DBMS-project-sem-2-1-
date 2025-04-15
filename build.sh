#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Check if we're using PostgreSQL or SQLite
if [ -n "$DATABASE_URL" ]; then
    echo "Using PostgreSQL database..."
    # Initialize PostgreSQL database
    python init_db.py
else
    echo "Using SQLite database..."
    # Create database directory if it doesn't exist
    mkdir -p database

    # Initialize the database if it doesn't exist
    if [ ! -f database/hostelmate.db ]; then
        echo "Initializing database..."
        python init_db.py
    fi
fi
