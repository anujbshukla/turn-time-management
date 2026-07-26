from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel, Field

class AppointmentCreate(BaseModel):
    appt_id: str
    appt_date: datetime
    customer_name: str | None = None
    customer_id: str | None = None
    facility_name: str | None = None
    facility_id: str | None = None
    scheduled_time: datetime
    carrier_name: str | None = None
    status: str | None = "Scheduled"

class CopilotWhatIfContext(BaseModel):
    selected_action_ids: list[int] = Field(
        default_factory=list,
    )

    extra_loaders: int = Field(
        default=0,
        ge=0,
        le=5,
    )

    extra_forklifts: int = Field(
        default=0,
        ge=0,
        le=5,
    )

    pre_stage_products: bool = False


from typing import Literal


class CopilotConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=4000,
    )


class AppointmentCopilotRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    what_if: CopilotWhatIfContext | None = None

    conversation_history: list[
        CopilotConversationMessage
    ] = Field(
        default_factory=list,
        max_length=20,
    )

    what_if: CopilotWhatIfContext | None = None


class CopilotFact(BaseModel):
    label: str
    value: str


class AppointmentCopilotResponse(BaseModel):
    appt_id: str
    answer: str
    facts: list[CopilotFact]
    suggested_questions: list[str]
class AppointmentResponse(AppointmentCreate):
    model_config = ConfigDict(from_attributes=True)

from typing import Literal
from pydantic import BaseModel, Field

DecisionStatus = Literal[
    "Pending",
    "Accepted",
    "Rejected",
]


class RecommendationActionDecision(BaseModel):
    recommendation_action_id: int

    decision_status: DecisionStatus

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )


class RecommendationDecisionRequest(BaseModel):
    actions: list[RecommendationActionDecision]

    decided_by: str = Field(
        default="Warehouse Supervisor",
        min_length=1,
        max_length=100,
    )



class WhatIfRequest(BaseModel):
    selected_action_ids: list[int] = Field(
        default_factory=list,
    )

    extra_loaders: int = Field(
        default=0,
        ge=0,
        le=5,
    )

    extra_forklifts: int = Field(
        default=0,
        ge=0,
        le=5,
    )

    pre_stage_products: bool = False


class WhatIfMetricSet(BaseModel):
    predicted_turn_time_minutes: float
    sla_minutes: int
    sla_miss_probability: float
    turn_risk_score: float
    detention_exposure: float


class WhatIfScenarioResult(BaseModel):
    projected_turn_time_minutes: float
    minutes_saved: float
    sla_recovered: bool
    projected_sla_miss_probability: float
    projected_recovery_probability: float
    projected_risk_score: float
    action_cost: float
    projected_detention_exposure: float
    gross_savings: float
    net_savings: float


class WhatIfResponse(BaseModel):
    appt_id: str
    selected_action_ids: list[int]
    baseline: WhatIfMetricSet
    scenario: WhatIfScenarioResult