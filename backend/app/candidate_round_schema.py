from typing import Literal

from pydantic import BaseModel, Field, model_validator


AttendanceStatus = Literal["Pending", "Present", "Absent"]
RoundResult = Literal["Pending", "Pass", "Fail", "On Hold"]


class CandidateRoundResultUpdate(BaseModel):
    attendance: AttendanceStatus
    result: RoundResult
    score: float | None = Field(default=None, ge=0, le=100)
    feedback: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_assessment(self):
        if self.result in {"Pass", "Fail", "On Hold"} and self.attendance == "Pending":
            raise ValueError("Mark attendance before recording a final round result")
        if self.result == "Pass" and self.attendance != "Present":
            raise ValueError("A candidate must be marked Present before recording Pass")
        if self.result == "On Hold" and self.attendance != "Present":
            raise ValueError("On Hold can only be recorded for a candidate marked Present")
        if self.score is not None and self.attendance != "Present":
            raise ValueError("A score can only be recorded when attendance is Present")
        return self
