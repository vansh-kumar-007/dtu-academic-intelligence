# scraper/pdf_parser.py
# Downloads and parses DTU result PDFs.
# Extracts student-level data: roll number, name, subjects, grades, SGPA.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import logging
import requests
import pdfplumber
import io

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# DTU grade to grade point mapping
GRADE_TO_POINTS = {
    "O":   10.0,
    "A+":   9.0,
    "A":    8.0,
    "B+":   7.0,
    "B":    6.0,
    "C":    5.0,
    "P":    4.0,
    "F":    0.0,
    "AB":   0.0,   # Absent
    "I":    0.0,   # Incomplete
}

# Roll number pattern: 23/ME/103 or 24/CO/045 etc
# DTU roll number patterns:
# Modern:  23/ME/103  or  24/IMSECO/01
# Legacy:  2K21/CO/045  or  2k20/ME/012
ROLL_PATTERN = re.compile(
    r"^(2[Kk]\d{2}/[A-Z]+/\d+|\d{2}/[A-Z]+/\d+)$"
)


def download_pdf(url: str) -> bytes | None:
    """Downloads a PDF and returns raw bytes."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download PDF: {url} — {e}")
        return None


def roman_to_int(roman: str) -> int | None:
    """Converts Roman numeral to integer. e.g. 'III' → 3"""
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
    result = 0
    prev = 0
    for char in reversed(roman.upper()):
        curr = values.get(char, 0)
        result += curr if curr >= prev else -curr
        prev = curr
    return result if result > 0 else None


def extract_pdf_metadata(pdf_bytes: bytes) -> dict:
    """
    Extracts header info from first page of PDF.
    Returns programme, branch, semester, notification_no, result_date.
    """
    metadata = {
        "programme":       None,
        "branch":          None,
        "semester":        None,
        "notification_no": None,
        "result_date":     None,
    }

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return metadata

            text = pdf.pages[0].extract_text() or ""

            for line in text.split("\n"):
                line = line.strip()

                # Notification number
                m = re.search(r"Notification No[:\s]+(\S+)", line, re.IGNORECASE)
                if m:
                    metadata["notification_no"] = m.group(1)

                # Result date
                m = re.search(
                    r"Result Declaration Date\s*:\s*(\d{1,2}-\w+-\d{4})",
                    line, re.IGNORECASE
                )
                if m:
                    metadata["result_date"] = m.group(1)

                # Semester
                m = re.search(r"\b([IVX]+)-SEMESTER\b", line, re.IGNORECASE)
                if m:
                    metadata["semester"] = roman_to_int(m.group(1))

                # Programme and branch
                if "bachelor of technology" in line.lower():
                    metadata["programme"] = "B.Tech"
                    m = re.search(r"Bachelor of Technology\((.+?)\)", line, re.IGNORECASE)
                    if m:
                        metadata["branch"] = m.group(1).strip()

                elif "master of technology" in line.lower():
                    metadata["programme"] = "M.Tech"
                    m = re.search(r"Master of Technology\((.+?)\)", line, re.IGNORECASE)
                    if m:
                        metadata["branch"] = m.group(1).strip()

                elif "master of business" in line.lower():
                    metadata["programme"] = "MBA"

                elif "integrated" in line.lower():
                    metadata["programme"] = "IMS"

    except Exception as e:
        logger.error(f"Metadata extraction error: {e}")

    return metadata


def parse_table(table: list) -> list[dict]:
    """
    Parses one table from a DTU result PDF.

    DTU table structure:
        Row 0: Subject names (merged header)
        Row 1: Column headers — Sr.No | Roll No. | Name | subj1 | subj2 | SGPA | TC | Failed
        Row 2: Credit weights for each subject
        Row 3+: One student per row

    Returns list of student dicts extracted from this table.
    """
    students = []

    if len(table) < 4:
        return students

    header_row = table[1]

    # Find column positions
    roll_idx = None
    name_idx = None
    sgpa_idx = None
    tc_idx   = None
    failed_idx = None
    subject_cols = []  # list of (col_index, subject_code)

    for i, cell in enumerate(header_row):
        cell_str = str(cell or "").strip().lower()

        if "roll" in cell_str:
            roll_idx = i
        elif "name" in cell_str:
            name_idx = i
        elif cell_str == "sgpa":
            sgpa_idx = i
        elif cell_str == "tc":
            tc_idx = i
        elif "failed" in cell_str:
            failed_idx = i
        elif cell_str and roll_idx is not None and name_idx is not None:
            # Any column after Name and before SGPA is a subject
            if sgpa_idx is None:
                subject_cols.append((i, str(cell or "").strip()))

    if roll_idx is None or name_idx is None:
        return students

    # Parse student rows (skip rows 0, 1, 2 — they are headers/credits)
    for row in table[3:]:
        if not row or len(row) <= name_idx:
            continue

        roll = str(row[roll_idx] or "").strip()

        # Validate roll number format: 23/ME/103
        if not ROLL_PATTERN.match(roll):
            continue

        name = str(row[name_idx] or "").strip()
        if not name:
            continue

        # SGPA
        sgpa = None
        if sgpa_idx and sgpa_idx < len(row):
            try:
                sgpa = float(str(row[sgpa_idx] or "").strip())
            except ValueError:
                pass

        # Total Credits
        total_credits = None
        if tc_idx and tc_idx < len(row):
            try:
                total_credits = int(str(row[tc_idx] or "").strip())
            except ValueError:
                pass

        # Failed Courses
        failed = ""
        if failed_idx and failed_idx < len(row):
            failed = str(row[failed_idx] or "").strip()

        # Subject grades
        subject_grades = {}
        for col_idx, subj_code in subject_cols:
            if col_idx < len(row):
                raw_grade = str(row[col_idx] or "").strip().upper()
                subject_grades[subj_code] = {
                    "letter":       raw_grade,
                    "grade_points": GRADE_TO_POINTS.get(raw_grade, None)
                }

        students.append({
            "roll_number":    roll,
            "name":           name,
            "sgpa":           sgpa,
            "total_credits":  total_credits,
            "failed_courses": failed,
            "has_backlog":    bool(failed and failed not in ["", "None", "-"]),
            "subject_grades": subject_grades,
        })

    return students


def parse_pdf(url: str) -> dict:
    """
    Full pipeline for one PDF.
    Downloads → extracts metadata → parses all tables → returns structured data.
    """
    result = {
        "url":      url,
        "metadata": {},
        "students": [],
        "success":  False,
        "error":    None,
    }

    pdf_bytes = download_pdf(url)
    if not pdf_bytes:
        result["error"] = "Download failed"
        return result

    result["metadata"] = extract_pdf_metadata(pdf_bytes)

    # Collect all students across all pages and all tables
    seen_rolls = set()
    all_students = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    rows = parse_table(table)
                    for student in rows:
                        roll = student["roll_number"]
                        if roll not in seen_rolls:
                            seen_rolls.add(roll)
                            all_students.append(student)

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"PDF parse error: {e}")
        return result

    result["students"] = all_students
    result["success"]  = len(all_students) > 0
    return result


if __name__ == "__main__":

    test_urls = [
        ("B.Tech ME III Revised",  "https://exam.dtu.ac.in/result_2026/O25_BTECH_III_R5_ME_1943.pdf"),
        ("M.Tech STE I Sem",       "https://exam.dtu.ac.in/result_2026/O25_MTECH_STE_I_1945.pdf"),
        ("IMS ECO III Sem",        "https://exam.dtu.ac.in/result_2026/O25_IMS_ECO_III_1946.pdf"),
    ]

    for label, url in test_urls:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

        result = parse_pdf(url)

        print(f"  Success   : {result['success']}")
        print(f"  Programme : {result['metadata'].get('programme')}")
        print(f"  Branch    : {result['metadata'].get('branch')}")
        print(f"  Semester  : {result['metadata'].get('semester')}")
        print(f"  Students  : {len(result['students'])}")

        if result["students"]:
            print(f"\n  First 3 students:")
            for s in result["students"][:3]:
                print(f"\n    Roll    : {s['roll_number']}")
                print(f"    Name    : {s['name']}")
                print(f"    SGPA    : {s['sgpa']}")
                print(f"    Credits : {s['total_credits']}")
                print(f"    Backlog : {s['has_backlog']}")
                print(f"    Grades  : {s['subject_grades']}")