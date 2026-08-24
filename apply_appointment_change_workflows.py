from pathlib import Path

ROOT = Path.cwd()

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find patch anchor: {label}")
    return text.replace(old, new, 1)

# backend/app/models.py
path = "backend/app/models.py"
text = read(path)
model_anchor = '''    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
'''
model_insert = '''    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    original_scheduled_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    is_rescheduled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    reschedule_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    rescheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    edit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_edited_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
'''
if "original_scheduled_time:" not in text:
    text = replace_once(text, model_anchor, model_insert, "Appointment model tracking fields")
write(path, text)

# backend/app/schemas.py
path = "backend/app/schemas.py"
text = read(path)
schema_anchor = '''class AppointmentUpdatedResponse(BaseModel):
    appt_id: str
    appointment: dict
    prediction: dict | None = None
    scoring_status: Literal["scored", "model_unavailable", "failed"]
    changed_fields: list[str] = Field(default_factory=list)
    message: str
'''
schema_insert = '''class AppointmentUpdatedResponse(BaseModel):
    appt_id: str
    appointment: dict
    prediction: dict | None = None
    scoring_status: Literal["scored", "model_unavailable", "failed"]
    changed_fields: list[str] = Field(default_factory=list)
    message: str


class AppointmentRescheduleRequest(BaseModel):
    scheduled_time: datetime
    reason: str = Field(min_length=3, max_length=500)


class AppointmentRescheduleResponse(BaseModel):
    appt_id: str
    previous_scheduled_time: datetime
    scheduled_time: datetime
    estimated_arrival_time: datetime | None = None
    original_scheduled_time: datetime
    is_rescheduled: bool
    reschedule_count: int
    rescheduled_at: datetime
    prediction: dict | None = None
    scoring_status: Literal["scored", "model_unavailable", "failed"]
    message: str
'''
if "class AppointmentRescheduleRequest" not in text:
    text = replace_once(text, schema_anchor, schema_insert, "Reschedule schemas")
write(path, text)

# backend/app/api/appointments.py
path = "backend/app/api/appointments.py"
text = read(path)
api_import_anchor = '''    AppointmentResponse,
    AppointmentUpdate,
    AppointmentUpdatedResponse,
'''
api_import_insert = '''    AppointmentResponse,
    AppointmentRescheduleRequest,
    AppointmentRescheduleResponse,
    AppointmentUpdate,
    AppointmentUpdatedResponse,
'''
if "AppointmentRescheduleRequest" not in text:
    text = replace_once(text, api_import_anchor, api_import_insert, "API reschedule imports")
api_endpoint_anchor = '''@router.patch(
    "/{appt_id}",
    response_model=AppointmentUpdatedResponse,
)
def update_appointment(
'''
api_endpoint_insert = '''@router.post(
    "/{appt_id}/reschedule",
    response_model=AppointmentRescheduleResponse,
)
def reschedule_appointment(
    appt_id: str,
    payload: AppointmentRescheduleRequest,
    service: AppointmentService = Depends(get_appointment_service),
) -> dict[str, Any]:
    return service.reschedule(appt_id, payload)


@router.patch(
    "/{appt_id}",
    response_model=AppointmentUpdatedResponse,
)
def update_appointment(
'''
if '"/{appt_id}/reschedule"' not in text:
    text = replace_once(text, api_endpoint_anchor, api_endpoint_insert, "Reschedule endpoint")
write(path, text)

# backend/app/repositories/appointment_repository.py
path = "backend/app/repositories/appointment_repository.py"
text = read(path)
queue_anchor = '''                    a.status,
                    a.pallet_count,
'''
queue_insert = '''                    a.status,
                    a.original_scheduled_time,
                    a.is_rescheduled,
                    a.reschedule_count,
                    a.rescheduled_at,
                    a.edit_count,
                    a.last_edited_at,
                    a.pallet_count,
'''
if text.count("a.original_scheduled_time,") == 0:
    text = replace_once(text, queue_anchor, queue_insert, "Queue tracking columns")
details_anchor = '''                    a.status,
                    a.appointment_type,
                    a.load_type,
'''
details_insert = '''                    a.status,
                    a.original_scheduled_time,
                    a.is_rescheduled,
                    a.reschedule_count,
                    a.rescheduled_at,
                    a.edit_count,
                    a.last_edited_at,
                    a.appointment_type,
                    a.load_type,
'''
if text.count("a.original_scheduled_time,") < 2:
    text = replace_once(text, details_anchor, details_insert, "Details tracking columns")
repo_anchor = '''    def replace_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
'''
repo_insert = '''    def reschedule_appointment(
        self,
        *,
        appt_id: str,
        scheduled_time: datetime,
        changed_at: datetime,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                UPDATE appointments
                SET
                    original_scheduled_time = COALESCE(original_scheduled_time, scheduled_time),
                    estimated_arrival_time =
                        CASE
                            WHEN estimated_arrival_time IS NULL THEN NULL
                            ELSE estimated_arrival_time + (CAST(:scheduled_time AS TIMESTAMP) - scheduled_time)
                        END,
                    scheduled_time = CAST(:scheduled_time AS TIMESTAMP),
                    appt_date = CAST(:scheduled_time AS TIMESTAMP),
                    is_rescheduled = TRUE,
                    reschedule_count = COALESCE(reschedule_count, 0) + 1,
                    rescheduled_at = CAST(:changed_at AS TIMESTAMP),
                    status = 'Scheduled',
                    updated_at = CAST(:changed_at AS TIMESTAMP)
                WHERE appt_id = :appt_id
                RETURNING
                    appt_id,
                    original_scheduled_time,
                    scheduled_time,
                    estimated_arrival_time,
                    is_rescheduled,
                    reschedule_count,
                    rescheduled_at;
                """
            ),
            {
                "appt_id": appt_id,
                "scheduled_time": scheduled_time,
                "changed_at": changed_at,
            },
        ).mappings().one()
        self.db.commit()
        return dict(row)

    def replace_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
'''
if "def reschedule_appointment(" not in text:
    text = replace_once(text, repo_anchor, repo_insert, "Repository reschedule method")
write(path, text)

# backend/app/services/appointment_service.py
path = "backend/app/services/appointment_service.py"
text = read(path)
service_import_anchor = 'from app.schemas import AppointmentCreate, AppointmentUpdate\n'
service_import_insert = '''from app.schemas import (
    AppointmentCreate,
    AppointmentRescheduleRequest,
    AppointmentUpdate,
)
'''
if "AppointmentRescheduleRequest" not in text:
    text = replace_once(text, service_import_anchor, service_import_insert, "Service reschedule imports")
update_anchor = '''        existing = self.get_by_id(appt_id)
        existing_details = self.repository.get_details(appt_id) or {}
        previous_prediction = existing_details.get("prediction")
        if existing.status == "Completed":
'''
update_insert = '''        existing = self.get_by_id(appt_id)
        existing_details = self.repository.get_details(appt_id) or {}
        previous_prediction = existing_details.get("prediction")

        incoming_schedule = payload.scheduled_time.replace(tzinfo=None)
        existing_schedule = existing.scheduled_time.replace(tzinfo=None)

        if incoming_schedule != existing_schedule:
            raise AppError(
                message=(
                    "Scheduled time cannot be changed with Edit Appointment. "
                    "Use the Reschedule action instead."
                ),
                code="USE_RESCHEDULE_WORKFLOW",
                status_code=409,
                details={"appt_id": appt_id},
            )

        if existing.status == "Completed":
'''
if "USE_RESCHEDULE_WORKFLOW" not in text:
    text = replace_once(text, update_anchor, update_insert, "Edit/reschedule separation")
changed_anchor = '''        if new_product_signature != old_product_signature:
            changed_fields.append("products")

        previous_values = {
'''
changed_insert = '''        if new_product_signature != old_product_signature:
            changed_fields.append("products")

        if changed_fields:
            values["edit_count"] = int(getattr(existing, "edit_count", 0) or 0) + 1
            values["last_edited_at"] = now

        previous_values = {
'''
if 'values["edit_count"]' not in text:
    text = replace_once(text, changed_anchor, changed_insert, "Edit counters")
create_anchor = '''    def create(self, payload: AppointmentCreate) -> dict[str, Any]:
'''
reschedule_method = '''    def reschedule(
        self,
        appt_id: str,
        payload: AppointmentRescheduleRequest,
    ) -> dict[str, Any]:
        existing = self.get_by_id(appt_id)

        if existing.status in {
            "Arrived",
            "Waiting",
            "Dock Assigned",
            "In Progress",
            "Completed",
        } or existing.actual_arrival_time is not None:
            raise AppError(
                message=(
                    "Appointments cannot be rescheduled after arrival "
                    "or after warehouse processing has started."
                ),
                code="APPOINTMENT_NOT_RESCHEDULABLE",
                status_code=409,
                details={"appt_id": appt_id, "status": existing.status},
            )

        previous_scheduled_time = existing.scheduled_time
        next_scheduled_time = payload.scheduled_time.replace(tzinfo=None)

        if next_scheduled_time == previous_scheduled_time:
            raise AppError(
                message="Choose a different appointment date/time.",
                code="SCHEDULE_UNCHANGED",
                status_code=400,
                details={"appt_id": appt_id},
            )

        existing_details = self.repository.get_details(appt_id) or {}
        previous_prediction = existing_details.get("prediction")
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            updated = self.repository.reschedule_appointment(
                appt_id=appt_id,
                scheduled_time=next_scheduled_time,
                changed_at=now,
            )
            self.repository.create_audit_event(
                appt_id=appt_id,
                event_type="APPOINTMENT_RESCHEDULED",
                event_time=now,
                notes=payload.reason.strip(),
                performed_by="Operations Planner",
                field_name="scheduled_time",
                old_value=previous_scheduled_time,
                new_value=next_scheduled_time,
                details={
                    "reason": payload.reason.strip(),
                    "reschedule_count": updated["reschedule_count"],
                    "original_scheduled_time": str(updated["original_scheduled_time"]),
                },
            )
            self.repository.supersede_pending_recommendations(appt_id)
        except AppError:
            raise
        except Exception as exc:
            self.repository.rollback()
            raise AppError(
                message=f"Unable to reschedule appointment: {exc}",
                code="APPOINTMENT_RESCHEDULE_FAILED",
                status_code=500,
                details={"appt_id": appt_id},
            ) from exc

        prediction = None
        scoring_status = "model_unavailable"
        message = (
            "Appointment rescheduled. ML-v2 artifacts are unavailable, "
            "so rescoring was skipped."
        )
        try:
            prediction = PredictionOrchestrationService(
                self.repository.db,
                self.repository,
            ).score_and_persist(appt_id)
            self.repository.create_audit_event(
                appt_id=appt_id,
                event_type="PREDICTION_UPDATED",
                event_time=now,
                notes="ML-v2 prediction recalculated after appointment reschedule.",
                performed_by="Warehouse ML-v2 Service",
                field_name="turn_risk_score",
                old_value=(previous_prediction or {}).get("turn_risk_score"),
                new_value=prediction["turn_risk_score"],
                details={
                    "previous_prediction": previous_prediction or {},
                    "new_prediction": prediction,
                    "model_version": prediction["model_version"],
                },
            )
            scoring_status = "scored"
            message = f"Appointment rescheduled and rescored by {prediction['model_version']}."
        except Exception:
            scoring_status = "failed"
            message = "Appointment rescheduled, but ML-v2 rescoring failed."

        return normalize_database_value({
            "appt_id": appt_id,
            "previous_scheduled_time": previous_scheduled_time,
            "scheduled_time": updated["scheduled_time"],
            "estimated_arrival_time": updated["estimated_arrival_time"],
            "original_scheduled_time": updated["original_scheduled_time"],
            "is_rescheduled": updated["is_rescheduled"],
            "reschedule_count": updated["reschedule_count"],
            "rescheduled_at": updated["rescheduled_at"],
            "prediction": prediction,
            "scoring_status": scoring_status,
            "message": message,
        })

    def create(self, payload: AppointmentCreate) -> dict[str, Any]:
'''
if "def reschedule(" not in text:
    text = replace_once(text, create_anchor, reschedule_method, "Reschedule service")
write(path, text)

# frontend/src/types/appointments.ts
path = "frontend/src/types/appointments.ts"
text = read(path)
list_anchor = '''  status: string;

  pallet_count: number;
'''
list_insert = '''  status: string;

  original_scheduled_time: string | null;
  is_rescheduled: boolean;
  reschedule_count: number;
  rescheduled_at: string | null;
  edit_count: number;
  last_edited_at: string | null;

  pallet_count: number;
'''
if "is_rescheduled: boolean;" not in text:
    text = replace_once(text, list_anchor, list_insert, "AppointmentListItem tracking fields")
response_anchor = '''export interface UpdateAppointmentResponse
  extends CreateAppointmentResponse {
  changed_fields: string[];
}
'''
response_insert = '''export interface UpdateAppointmentResponse
  extends CreateAppointmentResponse {
  changed_fields: string[];
}

export interface RescheduleAppointmentPayload {
  scheduled_time: string;
  reason: string;
}

export interface RescheduleAppointmentResponse {
  appt_id: string;
  previous_scheduled_time: string;
  scheduled_time: string;
  estimated_arrival_time: string | null;
  original_scheduled_time: string;
  is_rescheduled: boolean;
  reschedule_count: number;
  rescheduled_at: string;
  prediction: Record<string, unknown> | null;
  scoring_status: "scored" | "model_unavailable" | "failed";
  message: string;
}
'''
if "RescheduleAppointmentPayload" not in text:
    text = replace_once(text, response_anchor, response_insert, "Frontend reschedule types")
write(path, text)

# frontend/src/types/appointmentDetails.ts
path = "frontend/src/types/appointmentDetails.ts"
text = read(path)
details_type_anchor = '''    status: string;
    appointment_type: string | null;
'''
details_type_insert = '''    status: string;

    original_scheduled_time: string | null;
    is_rescheduled: boolean;
    reschedule_count: number;
    rescheduled_at: string | null;
    edit_count: number;
    last_edited_at: string | null;

    appointment_type: string | null;
'''
if "original_scheduled_time: string | null;" not in text:
    text = replace_once(text, details_type_anchor, details_type_insert, "Details tracking types")
write(path, text)

# frontend/src/services/appointments.ts
path = "frontend/src/services/appointments.ts"
text = read(path)
services_import_anchor = '''  PaginatedAppointmentsResponse,
  UpdateAppointmentPayload,
  UpdateAppointmentResponse,
'''
services_import_insert = '''  PaginatedAppointmentsResponse,
  RescheduleAppointmentPayload,
  RescheduleAppointmentResponse,
  UpdateAppointmentPayload,
  UpdateAppointmentResponse,
'''
if "RescheduleAppointmentPayload" not in text:
    text = replace_once(text, services_import_anchor, services_import_insert, "Appointments service imports")
if "export async function rescheduleAppointment(" not in text:
    text += '''\n\nexport async function rescheduleAppointment(\n  appointmentId: string,\n  payload: RescheduleAppointmentPayload,\n): Promise<RescheduleAppointmentResponse> {\n  const response = await fetch(\n    `${API_BASE_URL}/api/appointments/${appointmentId}/reschedule`,\n    {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify(payload),\n    },\n  );\n\n  if (!response.ok) {\n    const rawBody = await response.text();\n    let message = `Unable to reschedule appointment: ${response.status}`;\n    if (rawBody) {\n      try {\n        const body = JSON.parse(rawBody);\n        message = body?.message ?? body?.detail ?? message;\n      } catch {\n        message = rawBody;\n      }\n    }\n    throw new Error(message);\n  }\n\n  return response.json();\n}\n'''
write(path, text)

# frontend/src/components/AppointmentDetailsDrawer.tsx
path = "frontend/src/components/AppointmentDetailsDrawer.tsx"
text = read(path)
drawer_import_anchor = 'import { AppointmentCopilot } from "./AppointmentCopilot";\n'
drawer_import_insert = '''import { AppointmentCopilot } from "./AppointmentCopilot";\nimport { EditAppointmentDialog } from "./EditAppointmentDialog";\nimport { RescheduleAppointmentDialog } from "./RescheduleAppointmentDialog";\n'''
if "EditAppointmentDialog" not in text:
    text = replace_once(text, drawer_import_anchor, drawer_import_insert, "Drawer dialog imports")
state_anchor = '''    const [\n        preStageProducts,\n        setPreStageProducts,\n    ] = useState(false);\n'''
state_insert = '''    const [\n        preStageProducts,\n        setPreStageProducts,\n    ] = useState(false);\n\n    const [\n        editAppointmentOpen,\n        setEditAppointmentOpen,\n    ] = useState(false);\n\n    const [\n        rescheduleAppointmentOpen,\n        setRescheduleAppointmentOpen,\n    ] = useState(false);\n'''
if "editAppointmentOpen" not in text:
    text = replace_once(text, state_anchor, state_insert, "Drawer workflow state")
header_close_anchor = '''                    <button\n                        type="button"\n                        className="drawer-close"\n                        onClick={onClose}\n                        aria-label="Close"\n                    >\n                        ×\n                    </button>\n'''
header_actions = '''                    <div className="appointment-drawer-header-actions">\n                        {details && (\n                            <>\n                                <button\n                                    type="button"\n                                    className="secondary-button appointment-drawer-action"\n                                    disabled={details.appointment.status === "Completed"}\n                                    onClick={() => setEditAppointmentOpen(true)}\n                                >\n                                    Edit appointment\n                                </button>\n\n                                <button\n                                    type="button"\n                                    className="secondary-button appointment-drawer-action"\n                                    disabled={\n                                        details.appointment.status === "Arrived" ||\n                                        details.appointment.status === "Waiting" ||\n                                        details.appointment.status === "Dock Assigned" ||\n                                        details.appointment.status === "In Progress" ||\n                                        details.appointment.status === "Completed" ||\n                                        Boolean(details.appointment.actual_arrival_time)\n                                    }\n                                    onClick={() => setRescheduleAppointmentOpen(true)}\n                                >\n                                    Reschedule\n                                </button>\n                            </>\n                        )}\n\n                        <button\n                            type="button"\n                            className="drawer-close"\n                            onClick={onClose}\n                            aria-label="Close"\n                        >\n                            ×\n                        </button>\n                    </div>\n'''
if "appointment-drawer-header-actions" not in text:
    text = replace_once(text, header_close_anchor, header_actions, "Drawer action buttons")
dialog_anchor = '''            </aside>\n        </>\n    );\n}\n'''
dialog_insert = '''            </aside>\n\n            {details && (\n                <>\n                    <EditAppointmentDialog\n                        open={editAppointmentOpen}\n                        details={details}\n                        onClose={() => setEditAppointmentOpen(false)}\n                        onSaved={onRefresh}\n                    />\n\n                    <RescheduleAppointmentDialog\n                        open={rescheduleAppointmentOpen}\n                        appointment={details.appointment}\n                        onClose={() => setRescheduleAppointmentOpen(false)}\n                        onSaved={onRefresh}\n                    />\n                </>\n            )}\n        </>\n    );\n}\n'''
if "<EditAppointmentDialog" not in text:
    text = replace_once(text, dialog_anchor, dialog_insert, "Drawer dialog rendering")
write(path, text)

# frontend/src/components/AppointmentTable.tsx
path = "frontend/src/components/AppointmentTable.tsx"
text = read(path)
header_anchor = '''                  <SortableHeader\n                    field="turn_risk_score"\n                    label="Risk"\n'''
header_insert = '''                  <th>Change status</th>\n                  <SortableHeader\n                    field="turn_risk_score"\n                    label="Risk"\n'''
if "<th>Change status</th>" not in text:
    text = replace_once(text, header_anchor, header_insert, "Change status header")
cell_anchor = '''                      <td>\n                        <span\n                          className={`risk-badge ${riskClass}`}\n                        >\n'''
cell_insert = '''                      <td>\n                        <span\n                          className={`appointment-change-badge ${\n                            appointment.is_rescheduled\n                              ? "rescheduled"\n                              : appointment.edit_count > 0\n                                ? "edited"\n                                : "original"\n                          }`}\n                        >\n                          {appointment.is_rescheduled && appointment.edit_count > 0\n                            ? "Rescheduled · Edited"\n                            : appointment.is_rescheduled\n                              ? "Rescheduled"\n                              : appointment.edit_count > 0\n                                ? "Edited"\n                                : "Original"}\n                        </span>\n                      </td>\n                      <td>\n                        <span\n                          className={`risk-badge ${riskClass}`}\n                        >\n'''
if "appointment-change-badge" not in text:
    text = replace_once(text, cell_anchor, cell_insert, "Change status cell")
text = text.replace('colSpan={8}', 'colSpan={9}')
write(path, text)

# frontend/src/pages/OperationsPage.tsx
path = "frontend/src/pages/OperationsPage.tsx"
text = read(path)
placeholder_anchor = '''    status: "Loading",\n    pallet_count: 0,\n'''
placeholder_insert = '''    status: "Loading",\n    original_scheduled_time: null,\n    is_rescheduled: false,\n    reschedule_count: 0,\n    rescheduled_at: null,\n    edit_count: 0,\n    last_edited_at: null,\n    pallet_count: 0,\n'''
if "is_rescheduled: false" not in text:
    text = replace_once(text, placeholder_anchor, placeholder_insert, "Operations placeholder")
write(path, text)

# frontend/src/App.css
path = "frontend/src/App.css"
text = read(path)
marker = "/* APPOINTMENT EDIT / RESCHEDULE WORKFLOWS */"
if marker not in text:
    text = text.rstrip() + '''\n\n/* APPOINTMENT EDIT / RESCHEDULE WORKFLOWS */\n.appointment-drawer-header-actions {\n    display: flex;\n    align-items: center;\n    justify-content: flex-end;\n    gap: 8px;\n    flex-wrap: wrap;\n}\n\n.appointment-drawer-action {\n    min-height: 36px;\n    white-space: nowrap;\n}\n\n.appointment-change-drawer,\n.reschedule-appointment-drawer {\n    z-index: 1300;\n}\n\n.appointment-change-backdrop {\n    z-index: 1290;\n}\n\n.appointment-change-notice {\n    margin: 0 0 16px;\n    padding: 10px 12px;\n    border: 1px solid #d7deea;\n    border-radius: 8px;\n    background: #f7f9fc;\n    color: #5f6f88;\n    font-size: 12px;\n    line-height: 1.45;\n}\n\n.reschedule-appointment-form {\n    display: flex;\n    flex: 1;\n    min-height: 0;\n    flex-direction: column;\n    overflow: auto;\n    padding: 18px;\n}\n\n.reschedule-current-time {\n    margin-top: 8px;\n    font-size: 18px;\n    font-weight: 750;\n    color: #16233a;\n}\n\n.reschedule-reason-field {\n    grid-column: 1 / -1;\n}\n\n.reschedule-reason-field textarea {\n    width: 100%;\n    resize: vertical;\n    min-height: 92px;\n    box-sizing: border-box;\n    border: 1px solid #d7deea;\n    border-radius: 8px;\n    padding: 10px 12px;\n    color: #17233a;\n    background: #ffffff;\n    font: inherit;\n}\n\n.appointment-change-badge {\n    display: inline-flex;\n    align-items: center;\n    min-height: 24px;\n    padding: 0 9px;\n    border-radius: 999px;\n    font-size: 10px;\n    font-weight: 750;\n    white-space: nowrap;\n    border: 1px solid transparent;\n}\n\n.appointment-change-badge.original {\n    color: #63718a;\n    background: #f1f4f8;\n    border-color: #e0e5ed;\n}\n\n.appointment-change-badge.edited {\n    color: #3158a5;\n    background: #eef4ff;\n    border-color: #d9e5fb;\n}\n\n.appointment-change-badge.rescheduled {\n    color: #8a5a0a;\n    background: #fff7df;\n    border-color: #f2df9c;\n}\n'''
write(path, text)

print("Appointment edit/reschedule workflows patched successfully.")
