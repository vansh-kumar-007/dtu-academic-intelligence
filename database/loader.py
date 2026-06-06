# database/loader.py
# Reads our scraped CSV and loads all entries into PostgreSQL.
# Safe to run multiple times — skips duplicates automatically.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal, create_tables
from database.models import ResultNotification
from config.settings import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


def detect_programme(title: str) -> str:
    """
    Detects the academic programme from the result title.
    Returns a clean programme label.
    """
    title_lower = title.lower()

    if "ph.d" in title_lower or "phd" in title_lower:
        return "Ph.D"
    elif "m.tech" in title_lower or "mtech" in title_lower:
        return "M.Tech"
    elif "mba" in title_lower:
        return "MBA"
    elif "ims" in title_lower:
        return "IMS"
    elif "b.tech" in title_lower or "btech" in title_lower:
        return "B.Tech"
    elif "bba" in title_lower:
        return "BBA"
    elif "convocation" in title_lower:
        return "Convocation"
    else:
        return "Other"


def detect_flags(title: str) -> tuple[bool, bool]:
    """
    Detects whether a result is a revised or reappear result.
    Returns (is_revised, is_reappear).
    """
    title_lower = title.lower()
    is_revised  = any(kw in title_lower for kw in ["revised", "r1", "r2", "r3", "r4", "r5"])
    is_reappear = any(kw in title_lower for kw in ["reappear", "re-appear", "ex-student"])
    return is_revised, is_reappear


def parse_date(date_str: str):
    """
    Converts date string like "20/05/2026" to a Python date object.
    Returns None if the date is invalid.
    """
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def load_csv_to_db(csv_path: str) -> dict:
    """
    Loads all entries from a CSV file into the result_notifications table.

    Returns a summary dictionary with counts.
    """
    logger.info(f"Loading CSV: {csv_path}")

    # Read the CSV
    df = pd.read_csv(csv_path)
    logger.info(f"CSV loaded: {len(df)} rows")

    # Make sure tables exist
    create_tables()

    db: Session = SessionLocal()

    inserted  = 0
    skipped   = 0
    errors    = 0

    try:
        for _, row in df.iterrows():

            # Detect programme and flags from title
            title       = str(row.get("title", "")).strip()
            programme   = detect_programme(title)
            is_revised, is_reappear = detect_flags(title)
            date_str    = str(row.get("date", "")).strip()
            date_parsed = parse_date(date_str)

            # Build the model object
            entry = ResultNotification(
                session     = str(row.get("session", "")).strip() or None,
                title       = title,
                number      = str(row.get("number", "")).strip() or None,
                date        = date_str or None,
                date_parsed = date_parsed,
                links       = str(row.get("links", "")).strip() or None,
                link_count  = int(row.get("link_count", 0)),
                year_page   = str(row.get("year_page", "")).strip() or None,
                is_revised  = is_revised,
                is_reappear = is_reappear,
                programme   = programme,
                scraped_at  = datetime.utcnow(),
            )

            try:
                db.add(entry)
                db.commit()
                inserted += 1

            except IntegrityError:
                # This entry already exists — skip it
                db.rollback()
                skipped += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Error inserting row: {e}")
                errors += 1

        logger.info(f"Done. Inserted: {inserted} | Skipped: {skipped} | Errors: {errors}")

    finally:
        db.close()

    return {
        "inserted": inserted,
        "skipped":  skipped,
        "errors":   errors,
        "total":    len(df)
    }


def print_db_summary():
    """
    Queries the database and prints a summary of what's stored.
    """
    from sqlalchemy import func
    from database.models import ResultNotification

    db = SessionLocal()

    try:
        total      = db.query(ResultNotification).count()
        programmes = db.query(
            ResultNotification.programme,
            func.count(ResultNotification.id)
        ).group_by(ResultNotification.programme).all()

        revised    = db.query(ResultNotification).filter(
            ResultNotification.is_revised == True
        ).count()

        reappear   = db.query(ResultNotification).filter(
            ResultNotification.is_reappear == True
        ).count()

        print(f"\n{'='*55}")
        print(f"  DATABASE SUMMARY — result_notifications")
        print(f"{'='*55}")
        print(f"  Total entries   : {total}")
        print(f"  Revised results : {revised}")
        print(f"  Reappear results: {reappear}")
        print(f"\n  Breakdown by programme:")
        for prog, count in sorted(programmes, key=lambda x: -x[1]):
            print(f"    {prog:<20}: {count}")

    finally:
        db.close()


if __name__ == "__main__":

    # Find the most recent CSV in the data folder
    csv_files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and f.startswith("dtu_results_")
    ])

    if not csv_files:
        print("❌ No CSV files found. Run scraper/runner.py first.")
        sys.exit(1)

    latest = os.path.join(DATA_DIR, csv_files[-1])
    print(f"\n📂 Loading: {latest}\n")

    summary = load_csv_to_db(latest)

    print(f"\n{'='*55}")
    print(f"  LOAD SUMMARY")
    print(f"{'='*55}")
    print(f"  Total rows in CSV : {summary['total']}")
    print(f"  Inserted          : {summary['inserted']}")
    print(f"  Skipped (dupes)   : {summary['skipped']}")
    print(f"  Errors            : {summary['errors']}")

    print_db_summary()