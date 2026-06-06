# database/connection.py
# Manages the database connection.
# Every other file imports the session from here.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL
from database.models import Base

# The engine is the actual connection to PostgreSQL
engine = create_engine(
    DATABASE_URL,
    echo=False,       # Set True to see every SQL query (useful for debugging)
    pool_pre_ping=True  # Automatically reconnect if connection drops
)

# A session is how we interact with the database
# Think of it like a conversation with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """
    Creates all tables in the database if they don't exist.
    Safe to run multiple times — won't delete existing data.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully.")


def get_db():
    """
    Returns a database session.
    Always close the session after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    print("Creating database tables...")
    create_tables()

    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n📋 Tables in database:")
    for table in tables:
        print(f"   ✅ {table}")