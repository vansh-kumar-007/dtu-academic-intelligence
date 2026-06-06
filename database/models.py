# database/models.py
# Defines ALL database tables for the DTU Academic Intelligence Platform.
# SQLAlchemy translates these Python classes into real PostgreSQL tables.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, UniqueConstraint, Date
)
from sqlalchemy.orm import declarative_base, relationship

# Base is the parent class all our models inherit from
# Think of it as the foundation all tables are built on
Base = declarative_base()


class ResultNotification(Base):
    """
    Stores every result entry scraped from the DTU results page.
    This is the data we already scrape — now going into a real database.
    """
    __tablename__ = "result_notifications"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    session     = Column(String(100), nullable=True)
    title       = Column(Text, nullable=False)
    number      = Column(String(50), nullable=True)
    date        = Column(String(20), nullable=True)       # "20/05/2026"
    date_parsed = Column(Date, nullable=True)             # Actual date object
    links       = Column(Text, nullable=True)             # Pipe-separated URLs
    link_count  = Column(Integer, default=0)
    year_page   = Column(String(20), nullable=True)       # "current", "2024" etc
    is_revised  = Column(Boolean, default=False)          # Revised result?
    is_reappear = Column(Boolean, default=False)          # Reappear result?
    programme   = Column(String(50), nullable=True)       # "B.Tech", "M.Tech" etc
    scraped_at  = Column(DateTime, default=datetime.utcnow)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Prevent duplicate entries
    __table_args__ = (
        UniqueConstraint("title", "number", "date", name="uq_result_notification"),
    )

    def __repr__(self):
        return f"<ResultNotification {self.number}: {self.title}>"


class Student(Base):
    """
    Stores each unique DTU student identified by their roll number.
    Roll number is the primary key — it uniquely identifies every student.
    """
    __tablename__ = "students"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    roll_number = Column(String(20), unique=True, nullable=False, index=True)
    name        = Column(String(200), nullable=True)
    programme   = Column(String(50), nullable=True)   # B.Tech, M.Tech, IMS etc
    branch      = Column(String(100), nullable=True)  # COE, ME, ECE etc
    batch       = Column(String(10), nullable=True)   # "2022", "2023" etc
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # A student has many semester results
    semester_results = relationship(
        "SemesterResult",
        back_populates="student",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Student {self.roll_number}: {self.name}>"


class SemesterResult(Base):
    """
    Stores one semester's result for one student.
    Links a student to their performance in a specific semester.
    """
    __tablename__ = "semester_results"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    student_id       = Column(Integer, ForeignKey("students.id"), nullable=False)
    roll_number      = Column(String(20), nullable=False, index=True)
    notification_id  = Column(Integer, ForeignKey("result_notifications.id"), nullable=True)
    notification_no  = Column(String(50), nullable=True)   # e.g. "1946"
    session          = Column(String(100), nullable=True)  # e.g. "Nov-25(O-25)"
    semester         = Column(Integer, nullable=True)      # 1, 2, 3 ... 8
    sgpa             = Column(Float, nullable=True)
    cgpa             = Column(Float, nullable=True)
    total_credits    = Column(Integer, nullable=True)
    failed_courses   = Column(Text, nullable=True)         # Comma-separated
    has_backlog      = Column(Boolean, default=False)
    result_date      = Column(String(20), nullable=True)
    programme        = Column(String(50), nullable=True)
    branch           = Column(String(100), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student      = relationship("Student", back_populates="semester_results")
    notification = relationship("ResultNotification")
    subject_scores = relationship(
        "SubjectScore",
        back_populates="semester_result",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "roll_number", "notification_no",
            name="uq_semester_result"
        ),
    )

    def __repr__(self):
        return f"<SemesterResult {self.roll_number} Sem{self.semester} SGPA={self.sgpa}>"


class SubjectScore(Base):
    """
    Stores individual subject grades for one student in one semester.
    Each row = one subject for one student in one semester.
    """
    __tablename__ = "subject_scores"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    semester_result_id = Column(Integer, ForeignKey("semester_results.id"), nullable=False)
    roll_number        = Column(String(20), nullable=False, index=True)
    subject_code       = Column(String(20), nullable=True)   # e.g. "ME209m"
    subject_name       = Column(String(200), nullable=True)  # e.g. "Mechanics of Solids"
    grade_points       = Column(Float, nullable=True)        # e.g. 4.00, 8.00, 10.00
    created_at         = Column(DateTime, default=datetime.utcnow)

    semester_result = relationship("SubjectResult", back_populates="subject_scores")

    # Fix the relationship name
    semester_result = relationship("SemesterResult", back_populates="subject_scores")

    __table_args__ = (
        UniqueConstraint(
            "semester_result_id", "subject_code",
            name="uq_subject_score"
        ),
    )

    def __repr__(self):
        return f"<SubjectScore {self.roll_number} {self.subject_code}={self.grade_points}>"


class ScrapingLog(Base):
    """
    Tracks every time we run the scraper.
    Helps us monitor health, detect failures, and audit history.
    """
    __tablename__ = "scraping_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    started_at      = Column(DateTime, default=datetime.utcnow)
    finished_at     = Column(DateTime, nullable=True)
    pages_scraped   = Column(Integer, default=0)
    entries_found   = Column(Integer, default=0)
    entries_new     = Column(Integer, default=0)
    entries_skipped = Column(Integer, default=0)
    pdfs_processed  = Column(Integer, default=0)
    students_found  = Column(Integer, default=0)
    status          = Column(String(20), default="running")  # running/success/failed
    error_message   = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ScrapingLog {self.started_at} — {self.status}>"