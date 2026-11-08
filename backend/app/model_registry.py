"""Import all SQLAlchemy models so Alembic sees the complete metadata.

When a new model file is added to app/, add its import here as well.
Do not import app.main here: main.py has application-startup side effects.
"""

# User model and shared declarative Base metadata.
from app import models as _user_models  # noqa: F401

# Core student and placement entities.
from app.profile import Profile  # noqa: F401
from app.education import Education  # noqa: F401
from app.skill import Skill  # noqa: F401
from app.resume import Resume  # noqa: F401
from app.resume_file import UploadedResume  # noqa: F401
from app.job import Job  # noqa: F401
from app.application import Application  # noqa: F401
from app.job_eligibility import JobEligibility  # noqa: F401
from app.saved_job import SavedJob  # noqa: F401

# Company, cycle, drive, policy, and recruitment-round entities.
from app.company import Company  # noqa: F401
from app.placement_cycle import PlacementCycle  # noqa: F401
from app.placement_drive import CompanyRecruitmentDrive  # noqa: F401
from app.placement_policy import PlacementPolicy  # noqa: F401
from app.placement_round import PlacementRound  # noqa: F401
from app.candidate_round import CandidateRound  # noqa: F401
