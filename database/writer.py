# database/writer.py
# Saves parsed PDF data into PostgreSQL.
# Handles students, semester_results, and subject_scores tables.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal
from database.models import Student, SemesterResult, SubjectScore, ResultNotification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


def extract_batch_from_roll(roll_number: str) -> str | None:
    """
    Extracts the admission year (batch) from a roll number.

    Examples:
        23/ME/103   → "2023"
        2K21/CO/045 → "2021"
        24/STE/01   → "2024"
    """
    # Modern format: 23/ME/103
    m = re.match(r"^(\d{2})/", roll_number)
    if m:
        year_short = m.group(1)
        year_int = int(year_short)
        # 20 and above = 2020s, below 20 = unlikely but handle safely
        return f"20{year_short}" if year_int >= 20 else f"20{year_short}"

    # Legacy format: 2K21/CO/045
    m = re.match(r"^2[Kk](\d{2})/", roll_number)
    if m:
        return f"20{m.group(1)}"

    return None


def extract_branch_from_roll(roll_number: str) -> str | None:
    """
    Extracts the branch code from a roll number.

    Examples:
        23/ME/103   → "ME"
        2K21/CO/045 → "CO"
        24/IMSECO/01 → "IMSECO"
    """
    m = re.match(r"^\d{2}/([A-Z]+)/", roll_number)
    if m:
        return m.group(1)

    m = re.match(r"^2[Kk]\d{2}/([A-Z]+)/", roll_number)
    if m:
        return m.group(1)

    return None


def upsert_student(
    db: Session,
    roll_number: str,
    name: str,
    programme: str | None,
    branch_from_pdf: str | None
) -> Student:
    """
    Creates a new student record or updates existing one.
    'Upsert' = Update if exists, Insert if not.

    We never overwrite a name with an empty value.
    """
    student = db.query(Student).filter_by(roll_number=roll_number).first()

    batch  = extract_batch_from_roll(roll_number)
    branch = branch_from_pdf or extract_branch_from_roll(roll_number)

    if not student:
        student = Student(
            roll_number = roll_number,
            name        = name if name else None,
            programme   = programme,
            branch      = branch,
            batch       = batch,
        )
        db.add(student)
        db.flush()  # Get the ID without committing
        logger.debug(f"New student: {roll_number} — {name}")
    else:
        # Update name only if we have a better value
        if name and not student.name:
            student.name = name
        if branch and not student.branch:
            student.branch = branch
        if batch and not student.batch:
            student.batch = batch
        if programme and not student.programme:
            student.programme = programme

    return student


def save_semester_result(
    db: Session,
    student: Student,
    parsed_data: dict,
    student_record: dict,
    notification_id: int | None = None
) -> SemesterResult | None:
    """
    Saves one semester result for one student.
    Skips if this exact result already exists.
    """
    metadata     = parsed_data["metadata"]
    roll_number  = student_record["roll_number"]
    notif_no     = metadata.get("notification_no")

    # Check if this semester result already exists
    existing = db.query(SemesterResult).filter_by(
        roll_number     = roll_number,
        notification_no = notif_no
    ).first()

    if existing:
        return existing

    sem_result = SemesterResult(
        student_id      = student.id,
        roll_number     = roll_number,
        notification_id = notification_id,
        notification_no = notif_no,
        session         = None,  # Will be filled from notification later
        semester        = metadata.get("semester"),
        sgpa            = student_record.get("sgpa"),
        cgpa            = student_record.get("cgpa"),
        total_credits   = student_record.get("total_credits"),
        failed_courses  = student_record.get("failed_courses") or None,
        has_backlog     = student_record.get("has_backlog", False),
        result_date     = metadata.get("result_date"),
        programme       = metadata.get("programme"),
        branch          = metadata.get("branch"),
    )

    db.add(sem_result)
    db.flush()
    return sem_result


def save_subject_scores(
    db: Session,
    sem_result: SemesterResult,
    subject_grades: dict
) -> int:
    """
    Saves individual subject grades for one semester result.
    Returns count of subjects saved.
    """
    saved = 0

    for subject_code, grade_data in subject_grades.items():
        # Check if already exists
        existing = db.query(SubjectScore).filter_by(
            semester_result_id = sem_result.id,
            subject_code       = subject_code
        ).first()

        if existing:
            continue

        score = SubjectScore(
            semester_result_id = sem_result.id,
            roll_number        = sem_result.roll_number,
            subject_code       = subject_code,
            subject_name       = "",  # We'll enrich this later
            grade_points       = grade_data.get("grade_points"),
        )
        db.add(score)
        saved += 1

    return saved


def save_parsed_pdf(parsed_data: dict, notification_id: int | None = None) -> dict:
    """
    Main function — saves all data from one parsed PDF into the database.

    Args:
        parsed_data: Output from scraper/pdf_parser.py parse_pdf()
        notification_id: ID of the ResultNotification this PDF belongs to

    Returns:
        Summary dict with counts.
    """
    summary = {
        "students_new":      0,
        "students_updated":  0,
        "results_saved":     0,
        "results_skipped":   0,
        "subjects_saved":    0,
        "errors":            0,
    }

    if not parsed_data.get("success"):
        logger.warning("Parsed data marked as unsuccessful. Skipping.")
        return summary

    metadata  = parsed_data["metadata"]
    students  = parsed_data["students"]
    programme = metadata.get("programme")
    branch    = metadata.get("branch")

    logger.info(
        f"Saving {len(students)} students — "
        f"{programme} {branch} Sem {metadata.get('semester')}"
    )

    db = SessionLocal()

    try:
        for student_record in students:
            roll   = student_record["roll_number"]
            name   = student_record["name"]

            try:
                # 1. Upsert student
                was_new = db.query(Student).filter_by(roll_number=roll).first() is None
                student = upsert_student(db, roll, name, programme, branch)

                if was_new:
                    summary["students_new"] += 1
                else:
                    summary["students_updated"] += 1

                # 2. Save semester result
                sem_result = save_semester_result(
                    db, student, parsed_data,
                    student_record, notification_id
                )

                if sem_result:
                    if sem_result.id and db.is_modified(sem_result):
                        summary["results_saved"] += 1
                    else:
                        summary["results_saved"] += 1

                # 3. Save subject scores
                subjects_saved = save_subject_scores(
                    db, sem_result, student_record.get("subject_grades", {})
                )
                summary["subjects_saved"] += subjects_saved

                db.commit()

            except IntegrityError:
                db.rollback()
                summary["results_skipped"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving {roll}: {e}")
                summary["errors"] += 1

    finally:
        db.close()

    return summary


if __name__ == "__main__":
    from scraper.pdf_parser import parse_pdf

    test_pdfs = [
        ("B.Tech ME III", "https://exam.dtu.ac.in/result_2026/O25_BTECH_III_R5_ME_1943.pdf"),
        ("M.Tech STE I",  "https://exam.dtu.ac.in/result_2026/O25_MTECH_STE_I_1945.pdf"),
        ("IMS ECO III",   "https://exam.dtu.ac.in/result_2026/O25_IMS_ECO_III_1946.pdf"),
    ]

    total_students = 0
    total_subjects = 0

    for label, url in test_pdfs:
        print(f"\n{'='*55}")
        print(f"  Processing: {label}")
        print(f"{'='*55}")

        parsed = parse_pdf(url)
        print(f"  Students in PDF : {len(parsed['students'])}")

        summary = save_parsed_pdf(parsed)

        print(f"  Students new    : {summary['students_new']}")
        print(f"  Students updated: {summary['students_updated']}")
        print(f"  Results saved   : {summary['results_saved']}")
        print(f"  Subjects saved  : {summary['subjects_saved']}")
        print(f"  Errors          : {summary['errors']}")

        total_students += summary["students_new"]
        total_subjects += summary["subjects_saved"]

    print(f"\n{'='*55}")
    print(f"  TOTAL SUMMARY")
    print(f"{'='*55}")
    print(f"  New students    : {total_students}")
    print(f"  Subjects saved  : {total_subjects}")

    # Verify in database
    from database.connection import SessionLocal
    from database.models import Student, SemesterResult, SubjectScore

    db = SessionLocal()
    print(f"\n  Database counts:")
    print(f"  Students        : {db.query(Student).count()}")
    print(f"  Semester results: {db.query(SemesterResult).count()}")
    print(f"  Subject scores  : {db.query(SubjectScore).count()}")
    db.close()