
from sqlalchemy.orm import Session

from app.profile import Profile
from app.education import Education
from app.job_eligibility import JobEligibility


def normalize(value):
    """Normalize text for case-insensitive comparison."""
    if value is None:
        return ""

    return str(value).strip().casefold()


def evaluate_eligibility(
    db: Session,
    user_id: int,
    job_id: int
):
    """
    Compare one student's Profile and Education records
    against the eligibility criteria configured for a job.
    """

    criteria = db.query(JobEligibility).filter(
        JobEligibility.job_id == job_id
    ).first()

    # No eligibility criteria configured means
    # the job currently has no additional restrictions.
    if not criteria:
        return {
            "eligible": True,
            "criteria_configured": False,
            "reasons": []
        }

    reasons = []

    # ---------------------------------
    # GET STUDENT PROFILE
    # ---------------------------------

    profile = db.query(Profile).filter(
        Profile.user_id == user_id
    ).first()

    # ---------------------------------
    # CHECK BRANCH
    # ---------------------------------

    eligible_branches = criteria.eligible_branches or []

    if eligible_branches:

        if not profile or not profile.branch:
            reasons.append(
                "Your profile branch is missing. Please update your profile."
            )

        elif normalize(profile.branch) not in {
            normalize(branch) for branch in eligible_branches
        }:
            reasons.append(
                f"Your branch ({profile.branch}) is not eligible."
            )

    # ---------------------------------
    # GET STUDENT EDUCATION RECORDS
    # ---------------------------------

    education_records = db.query(Education).filter(
        Education.user_id == user_id
    ).all()

    if not education_records:
        reasons.append(
            "Please add your education details before applying."
        )

        return {
            "eligible": False,
            "criteria_configured": True,
            "reasons": reasons
        }

    # Start with all the student's education records.
    # Narrow the list so all academic requirements
    # must be satisfied by the same education record.
    matching_records = education_records

    # ---------------------------------
    # CHECK COURSE
    # ---------------------------------

    eligible_courses = criteria.eligible_courses or []

    if eligible_courses:

        matching_records = [
            record for record in matching_records
            if normalize(record.degree) in {
                normalize(course) for course in eligible_courses
            }
        ]

        if not matching_records:
            reasons.append(
                "Your course is not included in the eligible courses."
            )

    # ---------------------------------
    # CHECK GRADUATION YEAR
    # ---------------------------------

    graduation_years = criteria.graduation_years or []

    if graduation_years and matching_records:

        matching_records = [
            record for record in matching_records
            if record.graduation_year in graduation_years
        ]

        if not matching_records:
            reasons.append(
                "Your graduation year does not meet the requirement."
            )

    # ---------------------------------
    # CHECK MINIMUM CGPA
    # ---------------------------------

    if criteria.min_cgpa is not None and matching_records:

        cgpa_matches = []

        for record in matching_records:

            try:
                student_cgpa = float(record.cgpa)
            except (TypeError, ValueError):
                continue

            if student_cgpa >= criteria.min_cgpa:
                cgpa_matches.append(record)

        matching_records = cgpa_matches

        if not matching_records:
            reasons.append(
                f"Minimum required CGPA is {criteria.min_cgpa}."
            )

    # ---------------------------------
    # CHECK ACTIVE BACKLOGS
    # ---------------------------------

    if (
        criteria.max_active_backlogs is not None
        and matching_records
    ):

        matching_records = [
            record for record in matching_records
            if (
                record.active_backlogs is not None
                and record.active_backlogs
                <= criteria.max_active_backlogs
            )
        ]

        if not matching_records:
            reasons.append(
                "Your active backlogs exceed the permitted limit."
            )

    # ---------------------------------
    # FINAL RESULT
    # ---------------------------------

    is_eligible = (
        len(matching_records) > 0
        and len(reasons) == 0
    )

    return {
        "eligible": is_eligible,
        "criteria_configured": True,
        "reasons": reasons
    }
