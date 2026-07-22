# 🚚 AI-Powered Warehouse Turn Time Management

An intelligent warehouse operations platform that predicts appointment delays, calculates SLA risk, recommends operational actions, optimizes dock utilization, and leverages Machine Learning and Generative AI to improve warehouse turn time.

---

# Overview

This application helps warehouse operators proactively manage inbound and outbound appointments by combining:

- Machine Learning
- Generative AI
- Optimization Algorithms
- Real-time Operational KPIs

Instead of simply displaying warehouse metrics, the platform predicts future operational issues and recommends corrective actions before service levels are impacted.

---

# Core Capabilities

## Appointment Management

- Appointment scheduling
- Appointment tracking
- Carrier management
- Facility management
- Dock assignment

---

## Operational Intelligence

- Predict Late Appointments
- Predict Missed Appointments
- Turn Risk Score
- Remaining SLA Time
- SLA Recovery Probability
- Dock Utilization
- Dock Congestion Prediction
- Carrier Reliability Score
- Loading Sequence Optimization
- Monetary Loss Estimation

---

## Recommendation Engine

The application recommends:

- Best Next Action
- Best Dock Assignment
- Appointment Rescheduling
- Workforce Prioritization
- Loading Order Optimization
- SLA Recovery Plan

---

## Generative AI Features

Future phases include:

- AI Warehouse Assistant
- Natural Language Querying
- AI Shift Summaries
- AI Root Cause Analysis
- AI Operational Recommendations
- AI Appointment Explanations

---

# Technology Stack

## Frontend

- React
- TypeScript
- Vite

## Backend

- FastAPI
- Python 3.13

## Database

- PostgreSQL
- SQLAlchemy
- Alembic

## Infrastructure

- Docker
- Docker Compose

## Machine Learning (Planned)

- XGBoost
- LightGBM
- Scikit-learn
- OR-Tools

## Generative AI (Planned)

- Azure OpenAI
- LangChain
- Semantic Kernel
- RAG

---

# Project Structure

```
turn-time-management/

├── backend/
├── frontend/
├── database/
├── docs/
├── genai/
├── ml/
├── scripts/
└── README.md
```

---

# Local Development

## Prerequisites

- Python 3.13+
- Node.js LTS
- Docker Desktop
- Git
- VS Code

---

## Start PostgreSQL

```bash
docker compose up -d
```

---

## Start Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

---

## Start Frontend

```bash
cd frontend
npm run dev
```

---

# API Documentation

Swagger UI

```
http://127.0.0.1:8000/docs
```

Health Endpoint

```
http://127.0.0.1:8000/health
```

---

# Current Project Status

## Completed

- FastAPI Backend
- React Frontend
- PostgreSQL Integration
- SQLAlchemy ORM
- Centralized Configuration
- Structured Logging
- Database Schema
- Manual SQL Migrations

## In Progress

- Alembic Migrations
- Automated Tests

## Planned

- Machine Learning Models
- Optimization Engine
- Recommendation Engine
- Generative AI Assistant
- Authentication
- Role-Based Security
- CI/CD
- Kubernetes Deployment

---

# Future Roadmap

Phase 1

- Appointment CRUD
- Dashboard

Phase 2

- Operational KPIs

Phase 3

- Prediction Engine

Phase 4

- Recommendation Engine

Phase 5

- GenAI Copilot

Phase 6

- Production Deployment

---

# License

For demonstration and portfolio purposes.