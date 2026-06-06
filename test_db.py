# test_db.py — temporary file to verify database connection
# We will delete this after confirming the connection works

import sys
import os
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import create_engine, text
from config.settings import DATABASE_URL

print(f"Connecting to: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        print(f"\n✅ Connected successfully!")
        print(f"   PostgreSQL version: {version}")
except Exception as e:
    print(f"\n❌ Connection failed: {e}")