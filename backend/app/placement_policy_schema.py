from pydantic import BaseModel, Field


class PlacementPolicyBase(BaseModel):

    max_active_applications: int = Field(
        default=1,
        ge=1,
        le=100
    )

    allow_reapply_after_rejection: bool = True

    allow_reapply_after_withdrawal: bool = True

    allow_multiple_positions_same_drive: bool = False

    allow_withdraw_after_shortlisting: bool = False

    allow_applications_after_offer_release: bool = True

    lock_after_offer_acceptance: bool = True

    allow_reapply_after_offer_declined: bool = True


class PlacementPolicyCreate(PlacementPolicyBase):
    pass


class PlacementPolicyUpdate(PlacementPolicyBase):
    pass