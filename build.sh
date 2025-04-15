#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create database directory if it doesn't exist
mkdir -p database

# Initialize the database if it doesn't exist
if [ ! -f database/hostelmate.db ]; then
    echo "Initializing database..."
    python init_db.py
fi
