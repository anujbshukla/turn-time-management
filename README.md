# AI-Powered Warehouse Turn Time Management

An intelligent warehouse operations platform for predicting appointment risk, monitoring turn-time performance, optimizing dock operations, recommending recovery actions, and helping warehouse teams make operational decisions using AI, machine learning, simulation, and conversational analytics.

The application combines a React/TypeScript operational interface with a FastAPI backend, PostgreSQL operational data, predictive models, optimization services, What-If simulation, and an AI Warehouse Copilot.

---

## Overview

Warehouse appointment delays can cascade across docks, labor, carriers, customers, and subsequent appointments.

This platform is designed to detect those problems early and help operations teams decide what to do next.

The system provides:

- Live appointment monitoring
- Turn-time and SLA tracking
- Late-arrival detection
- Expected late-arrival prediction
- SLA-miss prediction
- Appointment risk scoring
- Dock and resource intelligence
- AI recovery recommendations
- What-If simulation
- Appointment editing and rescheduling
- Operational lifecycle simulation
- Carrier and customer intelligence
- Predictive operational analytics
- AI Warehouse Copilot
- Mission-based AI execution
- Learning from operational outcomes

The goal is not simply to report warehouse performance, but to help operators predict problems, evaluate alternatives, take action, and measure the result.

---

# Core Capabilities

## 1. Live Appointment Queue

The Live Appointment Queue provides an operational view of warehouse appointments.

Information includes:

- Appointment ID
- Customer
- Facility
- Carrier
- Appointment type
- Scheduled time
- Expected arrival
- Status
- Change status
- Turn risk
- SLA information

The queue supports:

- Server-side pagination
- Filtering
- Date selection
- Facility filtering
- Customer filtering
- Carrier filtering
- Appointment type filtering
- Risk filtering
- Server-side sorting

The default operational sort prioritizes appointments based on their current lifecycle and proximity to expected arrival.

Operational appointments such as In Progress and Arrived receive priority over completed appointments, while Scheduled and En Route appointments are ranked using expected-arrival proximity.

---

## 2. Appointment Details Drawer

Selecting an appointment opens a detailed operational drawer.

The drawer includes:

### Operational Status

- Status
- Priority
- Facility
- Dock
- Appointment type
- Appointment time
- Expected arrival
- Carrier
- Trailer
- Pallets
- SKUs
- Total weight

### Driver & Equipment

- Driver
- License
- License state
- Phone
- Tractor
- Trailer

### Route

- Origin name
- Origin city
- Origin state
- Destination name
- Destination city
- Destination state

### Shipment Items

Shipment-level product information associated with the appointment.

### Operational Timeline

- Scheduled
- Arrived
- Load/unload start
- Load/unload end
- Dispatch

### Turn-Time Intelligence

Turn Time:

```text
Load/Unload End Time - Appointment Time
```

Remaining Turn Time:

```text
(Appointment Time + SLA Time) - Current Time
```

Once loading or unloading has ended, Remaining Turn Time stops counting and displays `—`.

---

## 3. Appointment Editing

Warehouse users can edit appointment operational information without rescheduling the appointment.

Examples include:

- Customer
- Facility
- Carrier
- Dock
- Appointment type
- Load type
- Trailer
- Priority
- SLA
- Detention cost
- Shipment items
- Operational attributes

Edits are tracked separately from reschedules.

The queue identifies appointments that have been modified.

---

## 4. Appointment Rescheduling

Rescheduling is a separate operational workflow from editing.

When an appointment is rescheduled, the platform tracks:

- Original scheduled time
- Previous scheduled time
- New scheduled time
- Reschedule count
- Reschedule timestamp
- Reschedule reason
- Prediction refresh

The Live Appointment Queue identifies appointments as:

- Original
- Edited
- Rescheduled
- Edited + Rescheduled

Rescheduling triggers updated operational prediction where available.

---

## 5. Automated Demo Appointment Lifecycle

Because the demonstration environment is not connected to a live Warehouse Management System or Yard Management System, the application can automatically advance appointments through realistic operational states.

Example lifecycle:

```text
Scheduled
    ↓
En Route
    ↓
Arrived
    ↓
In Progress
    ↓
Completed
```

This keeps the demonstration environment operationally realistic without requiring a warehouse user to manually complete every appointment.

---

# SLA & Turn-Time Intelligence

## Late Arrivals

Actual late arrivals are determined using:

```text
actual_arrival_time > scheduled_time
```

## Expected Late Arrivals

For appointments that have not yet arrived:

```text
estimated_arrival_time > scheduled_time
```

The KPI separates actual late arrivals from appointments expected to arrive late.

## SLA Monitoring

The system evaluates appointment performance against the configured SLA and supports:

- Remaining SLA time
- SLA miss probability
- SLA recovery probability
- Actual SLA outcome
- Predicted SLA outcome
- Recovery recommendations

---

# AI Recovery Recommendations

The platform can recommend operational actions for appointments at risk of missing SLA.

Potential actions include:

- Dock reassignment
- Additional labor
- Additional forklifts
- Loading/unloading sequence changes
- Appointment prioritization
- Operational recovery actions

Each recommendation can contain:

- Recommended action
- Reason
- Estimated minutes saved
- Required resources
- Estimated action cost
- Estimated savings
- SLA recovery impact

Operators can individually:

- Accept
- Reject
- Leave Pending

recommended actions.

---

# What-If Simulation

The What-If engine allows operators to evaluate potential interventions before applying them.

Scenarios can evaluate operational effects such as:

- Additional labor
- Dock changes
- Resource changes
- Recovery actions
- Appointment adjustments

Simulation results can update:

- Projected turn time
- SLA recovery probability
- Operational risk
- Predicted losses
- Recovery potential

---

# Predictive Intelligence

The platform contains predictive operational intelligence for warehouse decision support.

Capabilities include:

- Predicted arrival time
- Predicted arrival delay
- Predicted loading/unloading duration
- SLA miss probability
- SLA recovery probability
- Turn risk score
- Predicted missed appointments
- Dock congestion intelligence
- Carrier-delay intelligence
- Detention-cost intelligence
- Turn-time forecasting

Predictions can be refreshed following operational changes such as appointment rescheduling.

---

# AI Prediction Center

The AI Prediction Center provides explainable operational forecasts.

Forecast categories include:

- SLA-miss risk
- Dock congestion
- Carrier delay
- Recovery probability
- Detention cost
- Turn-time performance

Forecasts can include:

- Confidence
- Trend direction
- Primary contributing factor
- Suggested mitigation

---

# Executive Intelligence

The Operations dashboard includes executive-level intelligence such as:

- Warehouse Health Score
- Executive AI briefing
- Operating-status indicators
- Priority appointment intelligence
- Critical appointment focus
- Predictive operating conditions

The purpose is to summarize warehouse conditions without requiring users to interpret every individual operational metric.

---

# AI Warehouse Copilot

The Global AI Warehouse Copilot provides conversational access to warehouse operational data.

Users can ask questions about topics such as:

- Late appointments
- SLA performance
- Dock risk
- Carrier performance
- Customer performance
- Appointment risk
- Recovery effectiveness
- Historical performance
- Resource conditions
- Operational comparisons

The Copilot is designed to answer using warehouse data rather than functioning as a generic chatbot.

It supports contextual conversation state so follow-up questions can retain operational scope where appropriate.

---

# AI Mission Center

The AI Mission Center supports more action-oriented AI workflows.

Mission capabilities include:

- Operational objective definition
- Recommended action generation
- What-If evaluation
- Mission execution
- Action tracking
- Outcome measurement
- Learning from completed actions

This extends the platform from descriptive analytics toward AI-assisted operational execution.

---

# Action Effectiveness Learning

The system can measure whether accepted recommendations actually improved operational outcomes.

Learning signals can include:

- Minutes saved
- SLA recovery
- Recommendation acceptance
- Recommendation rejection
- Action effectiveness
- Actual turn time
- Predicted vs actual performance

These outcomes can support future recommendation quality and operational learning.

---

# Dashboard

The Operations dashboard includes capabilities such as:

- KPI cards
- Live Appointment Queue
- Warehouse Health Score
- Executive Intelligence
- AI Prediction Center
- Operating Conditions
- Live What-If Simulation
- Dock intelligence
- Carrier intelligence
- Customer intelligence
- SLA analytics
- Turn-time analytics
- AI Warehouse Copilot
- AI Mission Center

Dashboard sections are designed to support both high-level operational monitoring and appointment-level investigation.

---

# Technology Stack

## Frontend

- React
- TypeScript
- Vite
- CSS
- Lucide React

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic

## Database

- PostgreSQL
- Docker

## AI / Analytics

The application contains services supporting:

- Predictive scoring
- ML-v2 operational prediction
- Recommendation generation
- Recovery planning
- What-If simulation
- Optimization
- Conversational warehouse analytics
- Mission execution
- Action-effectiveness learning
- Model monitoring and governance

---

# Repository Structure

```text
turn-time-management/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── engines/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── migrations/
│   ├── requirements.txt
│   └── pytest.ini
│
├── database/
│   ├── migrations/
│   └── seed/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── App.css
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── README.md
└── CHANGELOG.md
```

---

# Local Development

## Prerequisites

Install:

- Python
- Node.js / npm
- Docker Desktop
- PostgreSQL Docker container
- Git

---

# Backend Setup

From the repository:

```powershell
cd C:\turn-time-management\backend
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies when required:

```powershell
pip install -r requirements.txt
```

Start FastAPI:

```powershell
uvicorn app.main:app --reload --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

---

# Frontend Setup

```powershell
cd C:\turn-time-management\frontend
npm install
npm run dev
```

Vite will display the local application URL.

For production validation:

```powershell
npm run build
```

---

# Database

The development database runs in PostgreSQL using Docker.

Primary development database:

```text
turn_time
```

Docker container:

```text
turn-time-postgres
```

Database migrations are maintained in the repository and should be applied in sequence.

---

# Testing

## Backend

```powershell
cd C:\turn-time-management\backend
pytest
```

Current validated suite:

```text
115 passed
48 skipped
```

Skipped tests include capability/live-matrix scenarios that are intentionally not executed as part of the standard local test run.

## Frontend

```powershell
cd C:\turn-time-management\frontend
npm run build
```

The production build should complete successfully before changes are committed.

---

# Development Principles

The project follows several architectural principles:

1. Operational calculations should be centralized rather than duplicated across UI components.
2. Backend filtering and sorting should operate across the complete dataset rather than only the current page.
3. AI recommendations should explain why an action is recommended.
4. Prediction and actual operational outcomes should remain distinguishable.
5. Editing and rescheduling are separate workflows.
6. Operational changes should be auditable.
7. What-If simulation should not silently modify live operational data.
8. AI outputs should remain grounded in available warehouse data.
9. Demo automation should emulate external warehouse-system behavior without being confused with real WMS integration.
10. Tests should protect semantic and API contracts as capabilities evolve.

---

# Current Development Status

The platform currently supports the major end-to-end demonstration workflows:

```text
Monitor
   ↓
Predict
   ↓
Explain
   ↓
Recommend
   ↓
Simulate
   ↓
Decide
   ↓
Execute
   ↓
Measure
   ↓
Learn
```

The next development stages focus on codebase consolidation, UI maintainability, integration hardening, and production-oriented architecture.

---

# Project Purpose

This project demonstrates how AI can move warehouse operations beyond traditional reporting.

Instead of only answering:

> What happened?

the platform is designed to help answer:

> What is likely to happen?

> Why is it happening?

> What should we do?

> What happens if we take that action?

> Did the action actually work?

That decision-support loop is the core purpose of the AI-Powered Warehouse Turn Time Management platform.