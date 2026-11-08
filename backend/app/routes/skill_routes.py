from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies import get_current_student
from app.skill import Skill
from app.skill_schema import SkillCreate
from app.security import (
    oauth2_scheme,
    verify_token
)

router = APIRouter()

@router.post("/skill")
def create_skill(
    skill: SkillCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    new_skill = Skill(
        user_id=user.id,
        skill_name=skill.skill_name
    )

    db.add(new_skill)
    db.commit()

    return {
        "message": "Skill added successfully"
    }

@router.get("/skills")
def get_skills(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()

    return skills

@router.delete("/skill/{skill_id}")
def delete_skill(
    skill_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    skill = db.query(Skill).filter(
        Skill.id == skill_id,
        Skill.user_id == user.id
    ).first()

    if not skill:
        raise HTTPException(
            status_code=404,
            detail="Skill not found"
        )

    db.delete(skill)
    db.commit()

    return {
        "message": "Skill deleted successfully"
    }
