from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AppointmentProductCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=1, le=100000)


class AppointmentBookingProduct(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=100000)
    product_label: str | None = None
    sku: str | None = None


class AppointmentBookingDraft(BaseModel):
    customer_id: str | None = None
    customer_label: str | None = None
    carrier_id: str | None = None
    carrier_label: str | None = None
    facility_id: str | None = None
    facility_label: str | None = None
    assigned_dock_id: str | None = None
    assigned_dock_label: str | None = None
    scheduled_time: datetime | None = None
    appointment_type: Literal["Inbound", "Outbound"] | None = None
    load_type: str = "Palletized"
    priority: int = Field(default=1, ge=1, le=5)
    sla_minutes: int = Field(default=120, ge=15, le=1440)
    detention_cost_per_hour: float = Field(default=100.0, ge=0)
    products: list[AppointmentBookingProduct] = Field(default_factory=list)

    # Temporary product-resolution state used only while Copilot asks the
    # user to confirm a partial/fuzzy product match. These values are never
    # sent to the appointment-creation endpoint.
    pending_product_id: str | None = None
    pending_product_label: str | None = None
    pending_product_sku: str | None = None
    pending_product_quantity: int | None = Field(default=None, ge=1, le=100000)


class AppointmentCreate(BaseModel):
    customer_id: str | None = Field(default=None, max_length=100)
    customer_name: str | None = Field(default=None, max_length=100)
    facility_id: str = Field(min_length=1, max_length=100)
    carrier_id: str | None = Field(default=None, max_length=100)
    assigned_dock_id: str | None = Field(default=None, max_length=50)
    scheduled_time: datetime
    estimated_arrival_time: datetime | None = None
    status: str = Field(default="Scheduled", max_length=30)
    appointment_type: Literal["Inbound", "Outbound"]
    load_type: str | None = Field(default="Palletized", max_length=30)
    trailer_number: str | None = Field(default=None, max_length=50)
    pallet_count: int = Field(default=0, ge=0, le=500)
    sku_count: int = Field(default=0, ge=0, le=10000)
    total_weight: float | None = Field(default=None, ge=0)
    total_cube: float | None = Field(default=None, ge=0)
    priority: int = Field(default=1, ge=1, le=5)
    sla_minutes: int = Field(default=120, ge=15, le=1440)
    detention_cost_per_hour: float = Field(default=100.0, ge=0)
    distance_band: str | None = Field(default="Regional", max_length=30)
    traffic_severity: int = Field(default=0, ge=0, le=5)
    weather_severity: int = Field(default=0, ge=0, le=5)
    surge_indicator: bool = False
    products: list[AppointmentProductCreate] = Field(
        default_factory=list,
        max_length=100,
    )


class AppointmentUpdate(BaseModel):
    customer_id: str | None = Field(default=None, max_length=100)
    facility_id: str = Field(min_length=1, max_length=100)
    carrier_id: str | None = Field(default=None, max_length=100)
    assigned_dock_id: str | None = Field(default=None, max_length=50)
    scheduled_time: datetime
    estimated_arrival_time: datetime | None = None
    appointment_type: Literal["Inbound", "Outbound"]
    load_type: str | None = Field(default="Palletized", max_length=30)
    trailer_number: str | None = Field(default=None, max_length=50)
    priority: int = Field(default=1, ge=1, le=5)
    sla_minutes: int = Field(default=120, ge=15, le=1440)
    detention_cost_per_hour: float = Field(default=100.0, ge=0)
    distance_band: str | None = Field(default="Regional", max_length=30)
    traffic_severity: int = Field(default=0, ge=0, le=5)
    weather_severity: int = Field(default=0, ge=0, le=5)
    surge_indicator: bool = False
    products: list[AppointmentProductCreate] = Field(default_factory=list, max_length=100)


class AppointmentUpdatedResponse(BaseModel):
    appt_id: str
    appointment: dict
    prediction: dict | None = None
    scoring_status: Literal["scored", "model_unavailable", "failed"]
    changed_fields: list[str] = Field(default_factory=list)
    message: str


class AppointmentCreatedResponse(BaseModel):
    appt_id: str
    appointment: dict
    prediction: dict | None = None
    scoring_status: Literal["scored", "model_unavailable", "failed"]
    message: str


class AppointmentReferenceItem(BaseModel):
    id: str
    label: str
    facility_id: str | None = None




class AppointmentProductReferenceItem(BaseModel):
    id: str
    label: str
    sku: str
    category: str
    unit_of_measure: str
    unit_weight_lb: float
    unit_volume_cuft: float
    units_per_case: int
    cases_per_pallet: int

class AppointmentReferenceData(BaseModel):
    facilities: list[AppointmentReferenceItem] = Field(default_factory=list)
    customers: list[AppointmentReferenceItem] = Field(default_factory=list)
    carriers: list[AppointmentReferenceItem] = Field(default_factory=list)
    docks: list[AppointmentReferenceItem] = Field(default_factory=list)
    products: list[AppointmentProductReferenceItem] = Field(default_factory=list)

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

    # Structured analytics state produced by Global Copilot.
    #
    # Assistant messages can carry this state forward so follow-up
    # questions such as:
    #
    #   "Rank carriers by average delay"
    #   "What about inbound only?"
    #   "Now show the top 3"
    #
    # can reuse the previous analytical context without reparsing
    # the assistant's natural-language answer.
    canonical_query_state: dict[str, Any] | None = None


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



class CopilotQuickAction(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    action: Literal[
        "ask",
        "filter_appointments",
        "open_appointment",
        "run_what_if",
    ]
    prompt: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, str] = Field(default_factory=dict)


class CopilotFact(BaseModel):
    label: str
    value: str

class CopilotActionType(str, Enum):
    ANSWER = "answer"

    ACCEPT_ACTIONS = "accept_actions"

    REJECT_ACTIONS = "reject_actions"

    RUN_WHAT_IF = "run_what_if"

    FILTER_APPOINTMENTS = "filter_appointments"

    OPEN_APPOINTMENT = "open_appointment"

    BOOK_APPOINTMENT = "book_appointment"


class CopilotActionIntent(BaseModel):
    action: CopilotActionType

    action_ids: list[int] = Field(
        default_factory=list,
    )

    confirmation_required: bool = False

    response_message: str

    metadata: dict[str, str] = Field(
        default_factory=dict,
    )

    booking_draft: AppointmentBookingDraft | None = None

class AppointmentCopilotResponse(BaseModel):
    appt_id: str

    mode: Literal[
        "answer",
        "action",
    ] = "answer"

    answer: str

    facts: list[CopilotFact] = Field(
        default_factory=list,
    )

    suggested_questions: list[str] = Field(
        default_factory=list,
    )

    quick_actions: list[CopilotQuickAction] = Field(
        default_factory=list,
        max_length=8,
    )

    action_intent: CopilotActionIntent | None = None
    
class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appt_id: str
    appt_date: datetime
    customer_name: str | None = None
    customer_id: str | None = None
    facility_id: str
    carrier_id: str | None = None
    assigned_dock_id: str | None = None
    scheduled_time: datetime
    estimated_arrival_time: datetime | None = None
    status: str
    appointment_type: str | None = None
    load_type: str | None = None
    trailer_number: str | None = None
    pallet_count: int
    sku_count: int
    total_weight: float | None = None
    total_cube: float | None = None
    priority: int
    sla_minutes: int
    detention_cost_per_hour: float

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

class DashboardWhatIfRequest(BaseModel):
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

    facility_id: str | None = Field(
        default=None,
        max_length=50,
    )

    customer_id: str | None = Field(
        default=None,
        max_length=100,
    )

    carrier_id: str | None = Field(
        default=None,
        max_length=100,
    )

    appointment_type: Literal[
        "Inbound",
        "Outbound",
    ] | None = None

    # Exclusive operating-window boundaries, matching
    # the global dashboard filter contract.
    date_from: date | None = None
    date_to: date | None = None
# ==========================================================
# Global Dashboard Copilot
# ==========================================================

class GlobalCopilotRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    facility_id: str | None = Field(
        default=None,
        max_length=100,
    )

    customer_id: str | None = Field(
        default=None,
        max_length=100,
    )

    carrier_id: str | None = Field(
        default=None,
        max_length=100,
    )

    appointment_type: Literal["Inbound", "Outbound"] | None = None

    status: str | None = Field(
        default=None,
        max_length=50,
    )

    risk_level: str | None = Field(
        default=None,
        max_length=50,
    )

    date_from: date | None = None
    date_to: date | None = None

    conversation_history: list[
        CopilotConversationMessage
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    booking_draft: AppointmentBookingDraft | None = None


class GlobalCopilotResponse(BaseModel):
    mode: Literal[
        "answer",
        "action",
    ] = "answer"

    answer: str

    facts: list[CopilotFact] = Field(
        default_factory=list,
    )

    suggested_questions: list[str] = Field(
        default_factory=list,
    )

    quick_actions: list[CopilotQuickAction] = Field(
        default_factory=list,
        max_length=8,
    )

    action_intent: CopilotActionIntent | None = None

    canonical_query_state: dict[str, Any] | None = None
# ==========================================================
# Multi-Appointment Optimization
# ==========================================================

class OptimizationWindowRequest(BaseModel):
    facility_id: str | None = Field(default=None, max_length=100)
    customer_id: str | None = Field(default=None, max_length=100)
    carrier_id: str | None = Field(default=None, max_length=100)
    appointment_type: Literal["Inbound", "Outbound"] | None = None
    date_from: date | datetime | None = None
    date_to: date | datetime | None = None
    max_missions: int = Field(default=5, ge=1, le=10)

    # Optional mission-level What-If constraints. When omitted the optimizer
    # uses all actual resource headroom calculated from shifts/equipment.
    max_extra_loaders_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    max_extra_forklifts_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    max_staging_labor_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    allow_dock_reassignment: bool = True


class OptimizationMissionStatusRequest(BaseModel):
    status: Literal[
        "Proposed",
        "Accepted",
        "In Progress",
        "Completed",
        "Dismissed",
    ]


class OptimizationMissionAcceptRequest(BaseModel):
    facility_id: str = Field(max_length=100)
    customer_id: str | None = Field(default=None, max_length=100)
    carrier_id: str | None = Field(default=None, max_length=100)
    appointment_type: Literal["Inbound", "Outbound"] | None = None
    window_start: datetime
    window_end: datetime
    max_extra_loaders_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    max_extra_forklifts_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    max_staging_labor_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=20,
    )
    allow_dock_reassignment: bool = True
