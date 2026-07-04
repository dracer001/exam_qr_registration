"""
schemas.py - Validation for the ONLINE pre-registration API.

Course code / exam date are NOT part of this schema on purpose - they are
resolved server-side from the registration_token in the URL, so a student
can never register themselves against a course or date they don't belong to.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re

VALID_LEVELS = {"100", "200", "300", "400", "500", "600"}
MATRIC_PATTERN = re.compile(r'^\d{4}/\d{1,2}/[0-9A-Za-z]+$')


class StudentRegistrationCreate(BaseModel):
    matric_number: str = Field(..., min_length=1, max_length=50)
    student_name: str = Field(..., min_length=1, max_length=200)
    department: str = Field(..., min_length=1, max_length=100)
    level: str = Field(...)
    email: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    face_images: List[str] = Field(..., min_length=1, max_length=5)

    @field_validator('matric_number')
    @classmethod
    def validate_matric(cls, v: str) -> str:
        if not MATRIC_PATTERN.match(v):
            raise ValueError('Matric number must be in format YYYY/X/XXXXX (e.g., 2024/4/101180CT)')
        return v

    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in VALID_LEVELS:
            raise ValueError(f'Level must be one of {sorted(VALID_LEVELS)}')
        return v
