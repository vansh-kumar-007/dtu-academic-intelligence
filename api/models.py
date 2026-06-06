# api/models.py
# Pydantic models — define the shape of API responses.
# FastAPI uses these to validate and serialize data automatically.

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ResultNotificationOut(BaseModel):
    """Shape of a result notification in API responses."""
    id:          int
    session:     Optional[str]
    title:       str
    number:      Optional[str]
    date:        Optional[str]
    programme:   Optional[str]
    is_revised:  bool
    is_reappear: bool
    links:       Optional[str]

    class Config:
        from_attributes = True


class SubjectScoreOut(BaseModel):
    """Shape of one subject score."""
    subject_code:  Optional[str]
    subject_name:  Optional[str]
    grade_points:  Optional[float]

    class Config:
        from_attributes = True


class SemesterResultOut(BaseModel):
    """Shape of one semester result."""
    semester:       Optional[int]
    session:        Optional[str]
    sgpa:           Optional[float]
    cgpa:           Optional[float]
    total_credits:  Optional[int]
    failed_courses: Optional[str]
    has_backlog:    bool
    result_date:    Optional[str]
    notification_no: Optional[str]
    subject_scores: list[SubjectScoreOut] = []

    class Config:
        from_attributes = True


class StudentOut(BaseModel):
    """Full student profile shape."""
    roll_number:      str
    name:             Optional[str]
    programme:        Optional[str]
    branch:           Optional[str]
    batch:            Optional[str]
    semester_results: list[SemesterResultOut] = []

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    """Platform statistics."""
    total_notifications: int
    total_students:      int
    total_semester_results: int
    total_subject_scores: int
    students_by_programme: dict
    students_by_batch:     dict


class SearchResult(BaseModel):
    """One search result item."""
    id:        int
    title:     str
    session:   Optional[str]
    number:    Optional[str]
    date:      Optional[str]
    programme: Optional[str]
    links:     Optional[str]

    class Config:
        from_attributes = True