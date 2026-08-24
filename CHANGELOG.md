# Changelog

This document records major functional and architectural milestones for the AI-Powered Warehouse Turn Time Management platform.

The project has evolved iteratively. This changelog consolidates historical implementation notes that were previously stored across multiple root-level Markdown files.

---

# Current Platform

## Appointment Operations

### Live Appointment Queue

Implemented:

- Server-side appointment retrieval
- Pagination
- Facility filtering
- Customer filtering
- Carrier filtering
- Appointment-type filtering
- Risk filtering
- Date filtering
- Server-side sorting
- Operational default sorting
- Expected-arrival sorting
- Appointment lifecycle status
- Appointment change status

### Appointment Change Tracking

Appointments can be identified as:

- Original
- Edited
- Rescheduled
- Edited + Rescheduled

Change tracking includes:

- Original scheduled time
- Previous scheduled time
- Edit count
- Reschedule count
- Reschedule timestamp
- Operational audit events

---

## Appointment Details

The Appointment Details Drawer was expanded to include:

- Operational status
- Appointment type
- Facility
- Dock
- Carrier
- Trailer
- Pallets
- SKUs
- Total weight
- Driver information
- Equipment information
- Origin
- Destination
- Shipment items
- Operational timeline
- Turn-time intelligence
- SLA outcome
- AI recovery recommendations
- Recommendation decision workflow
- What-If verification

---

## Turn-Time Calculations

Turn Time was standardized as:

```text
Load/Unload End Time - Appointment Time
```

Remaining Turn Time was standardized as:

```text
(Appointment Time + SLA Time) - Current Time
```

Remaining Turn Time stops once loading/unloading has completed and displays `—`.

---

## Late Arrival Intelligence

Late Arrivals use actual arrival information:

```text
actual_arrival_time > scheduled_time
```

Expected Late Arrivals use ETA information for appointments that have not yet arrived:

```text
estimated_arrival_time > scheduled_time
```

The dashboard KPI distinguishes actual late arrivals from expected late arrivals.

---

## Appointment Edit Workflow

Added a dedicated Edit Appointment workflow.

Supported changes include operational appointment fields and shipment items.

Editing does not implicitly reschedule an appointment.

Edit actions are tracked independently.

---

## Appointment Reschedule Workflow

Added a dedicated Reschedule Appointment workflow.

Rescheduling records:

- Original scheduled time
- Previous scheduled time
- New scheduled time
- Reason
- Reschedule count
- Reschedule timestamp

Operational prediction is refreshed after rescheduling where available.

A timezone issue caused by converting facility-local `datetime-local` values to UTC in the frontend was corrected by preserving warehouse-local wall-clock timestamps.

---

## Demo Appointment Lifecycle

Added automatic demo appointment lifecycle progression to emulate external WMS/YMS operational updates.

Lifecycle:

```text
Scheduled
→ En Route
→ Arrived
→ In Progress
→ Completed
```

This allows completed appointments and realistic operational states to appear in the demonstration environment without manual warehouse-system integration.

---

# Live Appointment Queue Sorting

Server-side sorting was added across the complete filtered appointment dataset.

Originally supported sortable fields included:

- Appointment
- Customer
- Facility
- Carrier
- Scheduled
- Status
- Risk

Sorting was subsequently expanded as the queue evolved.

Column interaction supports ascending and descending sorting, while default operational ordering prioritizes appointments according to warehouse workflow.

The operational default was refined to prioritize active work and meaningful ETA proximity rather than simple chronological order.

Historical implementation notes for this capability were previously stored in `README_SORTING_UPDATE.md` and `README_MERGED_UPDATE.md`.

---

# Dashboard Intelligence

## Executive Intelligence — Release 2.0 Sprint 1

Added:

- Executive AI briefing
- Explainable Warehouse Health Score
- Live operating-status banner
- Top-priority appointment intelligence
- Critical appointment focus
- Responsive enterprise dashboard styling

Backend additions included Executive Intelligence generation and dashboard response integration.

No database migration was required for the original feature.

---

## Predictive Intelligence — Release 2.0 Sprint 2

Added the AI Prediction Center.

Forecast categories included:

- 60-minute SLA-miss forecast
- Dock-congestion forecast
- Carrier-delay forecast
- Recovery-probability forecast
- Detention-cost forecast
- Turn-time forecast

Forecast explanations included:

- Confidence
- Trend direction
- Primary factor
- Mitigation

Additional capabilities included:

- Portfolio risk matrix
- Appointment filter integration
- Predicted-versus-actual history
- What-If integration
- Dashboard prediction regeneration

The backend introduced predictive intelligence services and expanded dashboard prediction data.

No database migration was required for the original feature.

---

# Collapsible Dashboard Panels

Operational dashboard intelligence panels were made collapsible to reduce visual density.

Capabilities included:

- Closed-by-default intelligence panels
- Compact collapsed cards
- Full-width expanded panels
- Preserved Global AI Warehouse Copilot
- Responsive dashboard behavior

The implementation originally maintained separate collapsible abstractions. During codebase cleanup, unused duplicate abstractions were removed.

---

# AI Warehouse Copilot

The Copilot evolved from basic operational questions into a broader warehouse analytics interface.

Capabilities added over time include:

- Appointment analytics
- Arrival semantics
- Historical scope
- Comparison scope
- Operating scope
- Resource scope
- Action-effectiveness analytics
- Conversation state
- Canonical conversation state
- Semantic normalization
- Universal data queries

Regression tests protect major Copilot semantic contracts.

---

## Copilot Ranking Reliability

Ranking logic was hardened for small samples.

Changes included:

- Primary ranking requires at least five appointments when sufficiently sampled groups exist.
- Groups containing one to four appointments remain visible but are identified as limited samples.
- A limited-sample group does not become the confident leader solely because its raw metric is higher.
- If every group is below the minimum sample threshold, Copilot communicates limited evidence.
- Singular/plural appointment grammar was corrected.
- Regression tests were added for small-sample ranking behavior.

This information was previously stored in the root `README.md`.

---

# What-If Simulation

Dashboard and appointment-level What-If capabilities were added.

What-If simulation supports evaluation of operational interventions without silently modifying live appointment data.

Simulation can evaluate:

- Turn-time effects
- SLA recovery
- Resource changes
- Recovery actions
- Operational risk
- Cost implications

Dashboard What-If scenarios can regenerate relevant executive and predictive intelligence.

---

# AI Recovery Actions

Recovery recommendations were expanded from appointment-level suggestions into action-level decision support.

Actions can contain:

- Action title
- Description
- Recommendation reason
- Owner role
- Start-by time
- Estimated minutes saved
- Additional labor
- Additional forklifts
- Required equipment
- Required dock
- Estimated cost

Users can independently:

- Accept
- Reject
- Leave Pending

individual recovery actions.

---

# Mission Execution

AI mission capabilities were introduced to move the application beyond passive recommendations.

Mission functionality includes:

- Mission definition
- Action planning
- What-If evaluation
- Execution
- Learning
- Outcome tracking

Contract tests protect mission execution behavior.

---

# Action Effectiveness Learning

Learning functionality was added to evaluate whether operational recommendations actually worked.

Capabilities include:

- Recommendation-use tracking
- Accepted-action tracking
- Actual turn-time comparison
- SLA outcome measurement
- Action effectiveness
- Mission learning
- Operational feedback

---

# ML & Model Governance

Machine-learning functionality evolved to include:

- ML-v2 prediction
- Appointment scoring
- What-If scoring
- Prediction persistence
- Rescoring after operational changes
- Monitoring
- Governance
- Release-readiness validation

Prediction fields include:

- Predicted arrival time
- Predicted delay
- Predicted duration
- SLA miss probability
- SLA recovery probability
- Turn risk score
- Predicted missed status
- Model version

---

# Appointment Operational Intelligence

The Appointment Drawer was enhanced with operational information not originally available in the base appointment model.

Added data includes:

### Driver & Equipment

- Driver name
- License number
- License state
- Driver phone
- Tractor number
- Trailer number

### Route

- Origin name
- Origin city
- Origin state
- Destination name
- Destination city
- Destination state

### Shipment

- Pallet count
- SKU count
- Total weight
- Shipment items

Facility display was updated to use the actual facility name rather than a facility identifier where available.

---

# Date & Appointment Filters

The original predefined date selections:

- Previous 7 days
- Yesterday
- Today
- Tomorrow
- Next 7 days
- Custom date

were replaced with a date picker.

Today's date is selected by default.

Appointment type filtering was simplified so the default selection is:

```text
All
```

rather than presenting a combined Inbound & Outbound label.

---

# Warehouse Risk & Predictive UI

Historical development phases introduced operational visual intelligence including:

- Warehouse risk visualization
- Predictive timeline concepts
- Interactive AI cards
- Operating-condition intelligence

These capabilities were progressively incorporated into the broader Operations dashboard rather than remaining isolated feature experiments.

---

# Codebase Cleanup

## Cleanup Phase 1

Removed obsolete implementation artifacts after confirming they were not referenced by active application code.

Removed historical patch scripts:

- `apply_appointment_change_workflows.py`
- `apply_appointment_drawer_layout_fix.py`
- `apply_appointment_drawer_turn_time_followup.py`
- `apply_appointment_intelligence_patch.py`
- `apply_demo_appointment_lifecycle.py`
- `apply_operations_filter_date_picker.py`
- `apply_warehouse_agent_update.py`

Removed unused source files:

- `backend/app/engines/recovery_engine.py`
- `frontend/src/components/CollapsibleSection.tsx`

Validation after cleanup:

```text
Backend:
115 passed
48 skipped

Frontend:
Production build successful
```

The existing Vite large-chunk warning remains a performance/optimization concern rather than a build failure.

---

# Documentation Consolidation

Historical root documentation is being consolidated into:

```text
README.md
CHANGELOG.md
```

The README represents the current application.

The changelog preserves important historical implementation milestones.

This replaces the pattern of creating separate root Markdown files for each incremental feature patch or development phase.

---

# Future Engineering Cleanup

Planned maintainability work includes:

- Break up oversized `App.css`
- Organize styles by application domain
- Decompose oversized React components
- Review overlapping appointment metadata hooks
- Review small TypeScript type modules for sensible consolidation
- Reduce frontend JavaScript bundle size
- Introduce code splitting where useful
- Continue removing obsolete development artifacts
- Preserve API/service/repository domain separation
- Maintain regression tests during refactoring

The goal of cleanup is not simply to minimize the number of files. The goal is to maintain clear ownership, reduce duplication, remove obsolete artifacts, and keep modules appropriately sized.