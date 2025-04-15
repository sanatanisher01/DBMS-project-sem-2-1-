import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor

def get_db_connection():
    """
    Get a database connection based on environment variables.
    If DATABASE_URL is set, connect to PostgreSQL, otherwise use SQLite.
    """
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and database_url.startswith('postgres'):
        # PostgreSQL connection
        conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
        # Enable automatic conversion of PostgreSQL column names to lowercase
        conn.autocommit = False
        return conn
    else:
        # SQLite connection (for local development)
        os.makedirs('database', exist_ok=True)
        conn = sqlite3.connect('database/hostelmate.db')
        conn.row_factory = sqlite3.Row
        return conn

def close_db_connection(conn):
    """Close the database connection."""
    if conn:
        conn.close()

def commit_db_changes(conn):
    """Commit changes to the database."""
    if conn:
        conn.commit()

def is_postgres():
    """Check if we're using PostgreSQL."""
    database_url = os.environ.get('DATABASE_URL')
    return database_url and database_url.startswith('postgres')

def get_placeholder():
    """Get the appropriate placeholder for the current database."""
    return '%s' if is_postgres() else '?'

def adapt_query_for_db(query):
    """
    Adapt a query to work with both SQLite and PostgreSQL.
    SQLite uses ? as placeholders, PostgreSQL uses %s
    """
    if is_postgres():
        return query.replace('?', '%s')
    return query
