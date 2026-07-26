import { useState } from "react";

import { AppointmentDetailsDrawer } from "../components/AppointmentDetailsDrawer";
import { AppointmentTable } from "../components/AppointmentTable";
import { BestNextAction } from "../components/BestNextAction";
import { DashboardCharts } from "../components/DashboardCharts";
import { DockUtilization } from "../components/DockUtilization";
import { Header } from "../components/Header";
import { KpiCard } from "../components/KpiCard";

import {
  currentRecommendation,
  docks,
} from "../data/dockData";

import { useAppointmentDetails } from "../hooks/useAppointmentDetails";
import { useAppointments } from "../hooks/useAppointments";
import { useDashboard } from "../hooks/useDashboard";

import type {
  AppointmentFilters,
  AppointmentListItem,
} from "../types/appointments";

export function OperationsPage() {
  const [appointmentFilters, setAppointmentFilters] =
    useState<AppointmentFilters>({});

  const [
    selectedAppointment,
    setSelectedAppointment,
  ] = useState<AppointmentListItem | null>(null);

  const {
    appointments,
    pagination,
    pageSize,
    loading,
    error,
    goToPreviousPage,
    goToNextPage,
    changePageSize,
    refresh: refreshAppointments,
  } = useAppointments(appointmentFilters);

  const {
    details: appointmentDetails,
    loading: appointmentDetailsLoading,
    error: appointmentDetailsError,
    refresh: refreshAppointmentDetails,
  } = useAppointmentDetails(
    selectedAppointment?.appt_id,
  );

  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useDashboard();

  const isDashboardLoading =
    dashboardLoading && !dashboard;

  function handleRiskSelect(
    riskLevel: string,
  ) {
    setAppointmentFilters((current) => ({
      ...current,
      riskLevel:
        current.riskLevel === riskLevel
          ? undefined
          : riskLevel,
      outcome: undefined,
    }));
  }

  function handleOutcomeSelect(
    outcome: string,
  ) {
    setAppointmentFilters((current) => ({
      ...current,
      outcome:
        current.outcome === outcome
          ? undefined
          : outcome,
      riskLevel: undefined,
    }));
  }

  function clearAppointmentFilters() {
    setAppointmentFilters({});
  }

  function refreshOperationsData() {
    refreshAppointmentDetails();
    refreshAppointments();
    refreshDashboard();
  }

  const dashboardKpis = [
    {
      label: "Appointments",
      value: isDashboardLoading
        ? "…"
        : dashboard
          ? dashboard.summary.total_appointments.toLocaleString()
          : "—",
      detail: "Current demo operations",
    },
    {
      label: "Late Arrivals",
      value: isDashboardLoading
        ? "…"
        : dashboard
          ? dashboard.summary.late_arrivals.toLocaleString()
          : "—",
      detail: "Arrived after scheduled time",
    },
    {
      label: "SLA Misses",
      value: isDashboardLoading
        ? "…"
        : dashboard
          ? dashboard.summary.sla_misses.toLocaleString()
          : "—",
      detail: "Completed beyond SLA",
    },
    {
      label: "Late Turns Recovered",
      value: isDashboardLoading
        ? "…"
        : dashboard
          ? dashboard.summary.late_turned_on_time.toLocaleString()
          : "—",
      detail: "Late arrivals turned on time",
    },
    {
      label: "Recovered by Actions",
      value: isDashboardLoading
        ? "…"
        : dashboard
          ? dashboard.summary
            .late_recovered_with_recommendations
            .toLocaleString()
          : "—",
      detail: dashboard
        ? `${dashboard.summary.recovery_contribution_percent}% of recoveries`
        : "Recommendation contribution",
    },
  ];

  return (
    <>
      <Header />

      {dashboardError && (
        <div className="table-error">
          {dashboardError}
        </div>
      )}

      <section className="kpi-grid">
        {dashboardKpis.map((kpi) => (
          <KpiCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            detail={kpi.detail}
          />
        ))}
      </section>

      {dashboard && (
        <DashboardCharts
          lateOutcomes={
            dashboard.late_appointment_outcomes
          }
          riskDistribution={
            dashboard.risk_distribution
          }
          selectedRiskLevel={
            appointmentFilters.riskLevel
          }
          selectedOutcome={
            appointmentFilters.outcome
          }
          onRiskSelect={handleRiskSelect}
          onOutcomeSelect={handleOutcomeSelect}
        />
      )}

      {(appointmentFilters.riskLevel ||
        appointmentFilters.outcome) && (
          <div className="active-filter-banner">
            <div>
              <strong>
                Appointment filter:
              </strong>{" "}
              {appointmentFilters.riskLevel
                ? `${appointmentFilters.riskLevel} risk`
                : appointmentFilters.outcome}
            </div>

            <button
              type="button"
              onClick={
                clearAppointmentFilters
              }
            >
              Clear filter
            </button>
          </div>
        )}

      <section className="content-grid">
        <AppointmentTable
          appointments={appointments}
          pagination={pagination}
          pageSize={pageSize}
          loading={loading}
          error={error}
          onPreviousPage={
            goToPreviousPage
          }
          onNextPage={goToNextPage}
          onPageSizeChange={
            changePageSize
          }
          onAppointmentSelect={
            setSelectedAppointment
          }
          selectedAppointmentId={
            selectedAppointment?.appt_id
          }
        />

        <BestNextAction
          recommendation={
            currentRecommendation
          }
        />
      </section>

      <DockUtilization
        docks={docks}
      />

      <AppointmentDetailsDrawer
        selectedAppointment={
          selectedAppointment
        }
        details={appointmentDetails}
        loading={appointmentDetailsLoading}
        error={appointmentDetailsError}
        onRefresh={refreshOperationsData}
        onClose={() =>
          setSelectedAppointment(null)
        }
      />
    </>
  );
}

export default OperationsPage;