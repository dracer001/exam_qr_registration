"""
schemas.py - Validation for the ONLINE pre-registration API.

Course code / exam date are NOT part of this schema on purpose - they are
resolved server-side from the registration_token in the URL, so a student
can never register themselves against a course or date they don't belong to.

Student identity (name, department, level) is likewise NOT typed in here -
it comes from the master student record (see Phase 1), looked up by
matric number server-side. A student can only confirm who they already
are on file, never self-declare it.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re

VALID_LEVELS = {"100", "200", "300", "400", "500", "600"}
MATRIC_PATTERN = re.compile(r'^\d{4}/\d{1,2}/[0-9A-Za-z]+$')

# Angles collected during registration face capture. Five now instead of
# three - more angle variety helps recognition robustness more than just
# repeating the same angle. Order matters: index lines up with
# face_images in the payload below.
ANGLE_LABELS = [
    {"key": "front", "label": "Front"},
    {"key": "left", "label": "Left Profile"},
    {"key": "right", "label": "Right Profile"},
    {"key": "up", "label": "Tilt Up"},
    {"key": "down", "label": "Tilt Down"},
]


class StudentRegistrationCreate(BaseModel):
    matric_number: str = Field(..., min_length=1, max_length=50)
    proceed_anyway: bool = False
    face_images: List[str] = Field(..., min_length=len(ANGLE_LABELS), max_length=len(ANGLE_LABELS))

    @field_validator('matric_number')
    @classmethod
    def validate_matric(cls, v: str) -> str:
        if not MATRIC_PATTERN.match(v):
            raise ValueError('Matric number must be in format YYYY/X/XXXXX (e.g., 2024/4/101180CT)')
        return v
