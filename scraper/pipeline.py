# scraper/pipeline.py
# Full automated pipeline — processes ALL DTU result PDFs.
# Downloads, parses, and saves student data for every result notification.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
from datetime import datetime

from database.connection import SessionLocal
from database.models import ResultNotification, ScrapingLog, SemesterResult
from database.writer import save_parsed_pdf
from scraper.pdf_parser import parse_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)

# Programmes we skip — Ph.D PDFs are scanned images
SKIP_PROGRAMMES = {"Ph.D", "Convocation", "Other"}

# How long to wait between PDF downloads (be polite to DTU server)
DELAY_BETWEEN_PDFS = 1.5


def get_unprocessed_notifications(db) -> list[ResultNotification]:
    """
    Returns all result notifications that:
    1. Have a PDF link
    2. Are not Ph.D / Convocation / Other
    3. Have not been processed yet (no semester results exist for their notification_no)
    """
    # Get all notification numbers already processed
    processed_notif_nos = set(
        row[0] for row in
        db.query(SemesterResult.notification_no)
        .filter(SemesterResult.notification_no.isnot(None))
        .distinct()
        .all()
    )

    logger.info(f"Already processed notification numbers: {len(processed_notif_nos)}")

    # Get all notifications we should process
    notifications = (
        db.query(ResultNotification)
        .filter(
            ResultNotification.links.isnot(None),
            ResultNotification.links != "",
            ResultNotification.programme.notin_(SKIP_PROGRAMMES),
        )
        .order_by(ResultNotification.date_parsed.desc())
        .all()
    )

    # Filter out already processed ones
    unprocessed = [
        n for n in notifications
        if n.number not in processed_notif_nos
    ]

    logger.info(f"Total processable notifications : {len(notifications)}")
    logger.info(f"Already processed               : {len(processed_notif_nos)}")
    logger.info(f"Remaining to process            : {len(unprocessed)}")

    return unprocessed


def start_scraping_log(db) -> ScrapingLog:
    """Creates a new scraping log entry to track this run."""
    log = ScrapingLog(
        started_at = datetime.utcnow(),
        status     = "running"
    )
    db.add(log)
    db.commit()
    return log


def finish_scraping_log(db, log: ScrapingLog, summary: dict, status: str = "success"):
    """Updates the scraping log with final results."""
    log.finished_at     = datetime.utcnow()
    log.status          = status
    log.pages_scraped   = summary.get("pdfs_attempted", 0)
    log.pdfs_processed  = summary.get("pdfs_success", 0)
    log.students_found  = summary.get("students_new", 0)
    log.entries_new     = summary.get("results_saved", 0)
    log.entries_skipped = summary.get("results_skipped", 0)
    db.commit()


def run_pipeline(
    limit: int | None = None,
    delay: float = DELAY_BETWEEN_PDFS,
    dry_run: bool = False
) -> dict:
    """
    Main pipeline function.

    Args:
        limit   : Max number of PDFs to process (None = all)
        delay   : Seconds to wait between PDFs
        dry_run : If True, parse but don't save to database

    Returns:
        Summary dictionary with all counts.
    """
    summary = {
        "pdfs_attempted":  0,
        "pdfs_success":    0,
        "pdfs_failed":     0,
        "pdfs_no_students": 0,
        "students_new":    0,
        "results_saved":   0,
        "results_skipped": 0,
        "subjects_saved":  0,
        "errors":          0,
    }

    db = SessionLocal()
    log = start_scraping_log(db)

    try:
        notifications = get_unprocessed_notifications(db)

        if limit:
            notifications = notifications[:limit]

        total = len(notifications)
        print(f"\n{'='*65}")
        print(f"  DTU PDF PIPELINE")
        print(f"  Mode    : {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"  PDFs    : {total} to process")
        print(f"  Delay   : {delay}s between requests")
        print(f"{'='*65}\n")

        if total == 0:
            print("  ✅ Nothing to process. All notifications already done.")
            return summary

        for i, notification in enumerate(notifications, 1):

            # Get ALL PDF URLs from the pipe-separated links
            urls = [u.strip() for u in (notification.links or "").split("|") if u.strip()]
            if not urls:
                continue

            pdf_success = 0
            pdf_students = 0

            for url in urls:
                if not url.lower().endswith(".pdf"):
                    continue

                try:
                    parsed = parse_pdf(url)

                    if not parsed["success"]:
                        continue

                    student_count = len(parsed["students"])

                    if dry_run:
                        pdf_students += student_count
                        pdf_success += 1
                        continue

                    result = save_parsed_pdf(parsed, notification_id=notification.id)
                    pdf_success += 1
                    pdf_students += result["students_new"]
                    summary["students_new"]    += result["students_new"]
                    summary["results_saved"]   += result["results_saved"]
                    summary["results_skipped"] += result["results_skipped"]
                    summary["subjects_saved"]  += result["subjects_saved"]
                    summary["errors"]          += result["errors"]

                    time.sleep(delay)

                except KeyboardInterrupt:
                    print("\n\n  ⚠️  Interrupted by user. Progress saved.")
                    finish_scraping_log(db, log, summary, status="interrupted")
                    return summary

                except Exception as e:
                    summary["pdfs_failed"] += 1
                    summary["errors"] += 1
                    logger.error(f"Pipeline error on {url}: {e}")

            summary["pdfs_attempted"] += len(urls)
            summary["pdfs_success"]   += pdf_success

            if pdf_students > 0:
                print(f"          ✅ {pdf_students} students across {pdf_success} PDFs")
            else:
                print(f"          ⚠️  No students found in any PDF")
                summary["pdfs_no_students"] += 1

        finish_scraping_log(db, log, summary, status="success")

    except Exception as e:
        logger.error(f"Pipeline crashed: {e}")
        finish_scraping_log(db, log, summary, status="failed")
        raise

    finally:
        db.close()

    return summary


def print_final_summary(summary: dict):
    """Prints a clean final summary."""
    print(f"\n{'='*65}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*65}")
    print(f"  PDFs attempted   : {summary['pdfs_attempted']}")
    print(f"  PDFs successful  : {summary['pdfs_success']}")
    print(f"  PDFs no students : {summary['pdfs_no_students']}")
    print(f"  PDFs failed      : {summary['pdfs_failed']}")
    print(f"  New students     : {summary['students_new']}")
    print(f"  Results saved    : {summary['results_saved']}")
    print(f"  Subjects saved   : {summary['subjects_saved']}")
    print(f"  Errors           : {summary['errors']}")

    # Live database counts
    db = SessionLocal()
    from database.models import Student, SemesterResult, SubjectScore
    print(f"\n  Database totals:")
    print(f"  Students         : {db.query(Student).count()}")
    print(f"  Semester results : {db.query(SemesterResult).count()}")
    print(f"  Subject scores   : {db.query(SubjectScore).count()}")
    db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DTU PDF Pipeline")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max PDFs to process (default: all)"
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Seconds between requests (default: 1.5)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse but don't save to database"
    )
    args = parser.parse_args()

    summary = run_pipeline(
        limit   = args.limit,
        delay   = args.delay,
        dry_run = args.dry_run
    )

    print_final_summary(summary)