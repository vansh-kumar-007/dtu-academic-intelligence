# api/routes.py
# All API endpoints. Each function handles one URL route.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from database.connection import SessionLocal
from database.models import (
    ResultNotification, Student,
    SemesterResult, SubjectScore
)
from api.models import (
    ResultNotificationOut, StudentOut,
    StatsOut, SearchResult
)

router = APIRouter()


# --- Dependency ---
# This function gives each endpoint a database session
# and closes it automatically when the request is done
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────
# RESULT NOTIFICATION ENDPOINTS
# ─────────────────────────────────────────

@router.get("/results", response_model=list[ResultNotificationOut])
def get_all_results(
    skip:      int = Query(0, ge=0),
    limit:     int = Query(50, ge=1, le=500),
    programme: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns all result notifications.
    Supports pagination (skip/limit) and filtering by programme.
    """
    query = db.query(ResultNotification).order_by(
        desc(ResultNotification.date_parsed)
    )

    if programme:
        query = query.filter(ResultNotification.programme == programme)

    return query.offset(skip).limit(limit).all()


@router.get("/results/recent", response_model=list[ResultNotificationOut])
def get_recent_results(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Returns the most recent result notifications."""
    return (
        db.query(ResultNotification)
        .order_by(desc(ResultNotification.date_parsed))
        .limit(limit)
        .all()
    )


@router.get("/results/{result_id}", response_model=ResultNotificationOut)
def get_result_by_id(result_id: int, db: Session = Depends(get_db)):
    """Returns one result notification by its ID."""
    result = db.query(ResultNotification).filter(
        ResultNotification.id == result_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return result


# ─────────────────────────────────────────
# STUDENT ENDPOINTS
# ─────────────────────────────────────────

@router.get("/student/{roll_number:path}", response_model=StudentOut)
def get_student_profile(roll_number: str, db: Session = Depends(get_db)):
    """
    Returns a full student profile including all semester results
    and subject scores.

    Example: GET /student/23/ME/103
    """
    # Roll numbers contain slashes so we need to handle the URL carefully
    # FastAPI captures path parameters so 23/ME/103 works with path param
    student = (
        db.query(Student)
        .options(
            joinedload(Student.semester_results)
            .joinedload(SemesterResult.subject_scores)
        )
        .filter(Student.roll_number == roll_number)
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"Student with roll number '{roll_number}' not found"
        )

    return student


@router.get("/students", response_model=list[dict])
def get_students(
    programme: str  = Query(None),
    branch:    str  = Query(None),
    batch:     str  = Query(None),
    skip:      int  = Query(0, ge=0),
    limit:     int  = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Returns a list of students with optional filters.
    """
    query = db.query(
        Student.roll_number,
        Student.name,
        Student.programme,
        Student.branch,
        Student.batch
    )

    if programme:
        query = query.filter(Student.programme == programme)
    if branch:
        query = query.filter(Student.branch.ilike(f"%{branch}%"))
    if batch:
        query = query.filter(Student.batch == batch)

    results = query.order_by(Student.roll_number).offset(skip).limit(limit).all()

    return [
        {
            "roll_number": r.roll_number,
            "name":        r.name,
            "programme":   r.programme,
            "branch":      r.branch,
            "batch":       r.batch,
        }
        for r in results
    ]


# ─────────────────────────────────────────
# SEARCH ENDPOINT
# ─────────────────────────────────────────

@router.get("/search", response_model=list[SearchResult])
def search(
    q:     str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Searches result notifications by title.
    Example: GET /search?q=B.Tech COE Sem 4
    """
    results = (
        db.query(ResultNotification)
        .filter(ResultNotification.title.ilike(f"%{q}%"))
        .order_by(desc(ResultNotification.date_parsed))
        .limit(limit)
        .all()
    )
    return results


@router.get("/search/student", response_model=list[dict])
def search_student(
    q:     str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Searches students by name or roll number.
    Example: GET /search/student?q=DHRUV
    """
    results = (
        db.query(Student)
        .filter(
            Student.name.ilike(f"%{q}%") |
            Student.roll_number.ilike(f"%{q}%")
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "roll_number": s.roll_number,
            "name":        s.name,
            "programme":   s.programme,
            "branch":      s.branch,
            "batch":       s.batch,
        }
        for s in results
    ]


# ─────────────────────────────────────────
# STATS ENDPOINT
# ─────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """Returns platform-wide statistics."""

    # Students by programme
    prog_rows = (
        db.query(Student.programme, func.count(Student.id))
        .group_by(Student.programme)
        .all()
    )

    # Students by batch
    batch_rows = (
        db.query(Student.batch, func.count(Student.id))
        .filter(Student.batch.isnot(None))
        .group_by(Student.batch)
        .order_by(Student.batch.desc())
        .all()
    )

    return StatsOut(
        total_notifications    = db.query(ResultNotification).count(),
        total_students         = db.query(Student).count(),
        total_semester_results = db.query(SemesterResult).count(),
        total_subject_scores   = db.query(SubjectScore).count(),
        students_by_programme  = {p or "Unknown": c for p, c in prog_rows},
        students_by_batch      = {b: c for b, c in batch_rows},
    )