import { useEffect, useState } from "react";
import { AppointmentDetailsDrawer } from "../components/AppointmentDetailsDrawer";
import { CreateAppointmentDrawer } from "../components/CreateAppointmentDrawer";
import { AppointmentTable } from "../components/AppointmentTable";
import { AiMissionCenter } from "../components/AiMissionCenter";
import { AiActionCardsPanel } from "../components/AiActionCardsPanel";
import { AiOperationsFeed } from "../components/AiOperationsFeed";
import { CollapsibleDashboardSection } from "../components/CollapsibleDashboardSection";
import { DashboardCharts } from "../components/DashboardCharts";
import { DockUtilization } from "../components/DockUtilization";
import { WarehouseRiskHeatMap } from "../components/WarehouseRiskHeatMap";
import {
  OperationsFilterBar,
  getComparisonRange,
  getPresetRange,
  getWeekComparisonRanges,
  type OperationsGlobalFilters,
} from "../components/OperationsFilterBar";
import {
  RootCauseIntelligenceSection,
  type IntelligenceFilters,
} from "../components/RootCauseIntelligenceSection";
import { PredictiveTimeline } from "../components/PredictiveTimeline";
import { ExecutiveOperationsCenter } from "../components/ExecutiveOperationsCenter";
import { GlobalWarehouseCopilot } from "../components/GlobalWarehouseCopilot";
import { Header } from "../components/Header";
import { IntelligentKpiCard } from "../components/IntelligentKpiCard";
import { KpiCard } from "../components/KpiCard";
import { LiveWhatIfDashboard } from "../components/LiveWhatIfDashboard";
import { OperationalAlertsPanel } from "../components/OperationalAlertsPanel";
import { PredictionCenter } from "../components/PredictionCenter/PredictionCenter";
import { MLModelHealth } from "../components/MLModelHealth";
import { RecommendationSavings } from "../components/RecommendationSavings";
import { SectionHeading } from "../components/SectionHeading";

import { useAppointmentDetails } from "../hooks/useAppointmentDetails";
import { useAppointmentFilterOptions } from "../hooks/useAppointmentFilterOptions";
import { useAppointments } from "../hooks/useAppointments";
import { useDashboard } from "../hooks/useDashboard";
import {
  useDashboardIntelligence,
  useDashboardIntelligenceFilterOptions,
} from "../hooks/useDashboardIntelligence";
import { useDashboardWhatIf } from "../hooks/useDashboardWhatIf";

import type {
  AppointmentFilters,
  AppointmentListItem,
  AppointmentReferenceData,
  AppointmentReferenceItem,
  CreateAppointmentResponse,
} from "../types/appointments";

type OperationsTab = "operations" | "recommendations" | "predictions" | "docks";

interface OperationsPageProps {
  facilityId?: string;
  referenceData: AppointmentReferenceData;
  onAvailableFacilitiesChange?: (facilities: AppointmentReferenceItem[]) => void;
}

export function OperationsPage({
  facilityId,
  referenceData,
  onAvailableFacilitiesChange,
}: OperationsPageProps) {
  const [globalFilters, setGlobalFilters] =
    useState<OperationsGlobalFilters>({
      datePreset: "today",
      compareMode: "off",
    });

  const [appointmentFilters, setAppointmentFilters] =
    useState<AppointmentFilters>(() => {
      const initialDateRange = getPresetRange("today");
      return {
        facilityId,
        dateFrom: initialDateRange.dateFrom,
        dateTo: initialDateRange.dateTo,
      };
    });

  const [intelligenceFilters, setIntelligenceFilters] =
    useState<IntelligenceFilters>(() => {
      const { dateFrom, dateTo } = getLastMonthRange();
      return {
        facilityId,
        dateFrom,
        dateTo,
      };
    });

  const [
    selectedAppointment,
    setSelectedAppointment,
  ] = useState<AppointmentListItem | null>(null);

  const [createAppointmentOpen, setCreateAppointmentOpen] = useState(false);
  const [kpiCardsExpanded, setKpiCardsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<OperationsTab>("operations");
  const [aiWorkspaceExpanded, setAiWorkspaceExpanded] = useState(true);
  const [capacityView, setCapacityView] = useState<"dock-utilization" | "risk-heatmap">("dock-utilization");
  const [dashboardWhatIfRequest, setDashboardWhatIfRequest] = useState<{
    extra_loaders: number;
    extra_forklifts: number;
    pre_stage_products: boolean;
  } | null>(null);

  const {
    appointments,
    pagination,
    pageSize,
    sortBy,
    sortDirection,
    loading,
    error,
    goToPreviousPage,
    goToNextPage,
    changePageSize,
    changeSort,
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

  const activeDateRange = getPresetRange(
    globalFilters.datePreset,
    globalFilters.customDate,
    globalFilters.customDateEnd,
  );

  const { options: filterOptions, loading: filterOptionsLoading } =
    useAppointmentFilterOptions({
      facilityId,
      customerId: globalFilters.customerId,
      carrierId: globalFilters.carrierId,
      appointmentType: globalFilters.appointmentType,
      dateFrom: activeDateRange.dateFrom,
      dateTo: activeDateRange.dateTo,
    });

  const availableCustomers = filterOptionsLoading
    ? referenceData.customers
    : filterOptions.customers;
  const availableCarriers = filterOptionsLoading
    ? referenceData.carriers
    : filterOptions.carriers;
  const availableAppointmentTypes = filterOptionsLoading
    ? [
      { id: "Inbound", label: "Inbound", facility_id: null },
      { id: "Outbound", label: "Outbound", facility_id: null },
    ]
    : filterOptions.appointmentTypes;

  const {
    options: intelligenceFilterOptions,
    loading: intelligenceFilterOptionsLoading,
  } = useDashboardIntelligenceFilterOptions({
    facilityId,
    customerId: intelligenceFilters.customerId,
    carrierId: intelligenceFilters.carrierId,
    appointmentType: intelligenceFilters.appointmentType,
    dateFrom: intelligenceFilters.dateFrom,
    dateTo: intelligenceFilters.dateTo,
  });

  const intelligenceReferenceData = intelligenceFilterOptions;

  const dashboardFilters = {
    facilityId,
    customerId: globalFilters.customerId,
    carrierId: globalFilters.carrierId,
    appointmentType: globalFilters.appointmentType,
    dateFrom: activeDateRange.dateFrom,
    dateTo: activeDateRange.dateTo,
  };

  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useDashboard(dashboardFilters);

  const weekComparisonRanges = getWeekComparisonRanges();

  const {
    dashboard: currentWeekDashboard,
    loading: currentWeekLoading,
  } = useDashboard(
    {
      facilityId,
      customerId: globalFilters.customerId,
      carrierId: globalFilters.carrierId,
      appointmentType: globalFilters.appointmentType,
      dateFrom: weekComparisonRanges.current.dateFrom,
      dateTo: weekComparisonRanges.current.dateTo,
    },
    globalFilters.compareMode === "previous-week",
  );

  const comparisonRange = getComparisonRange(
    globalFilters.datePreset,
    globalFilters.compareMode,
    globalFilters.customDate,
    globalFilters.customDateEnd,
  );

  const {
    dashboard: comparisonDashboard,
    loading: comparisonLoading,
  } = useDashboard(
    {
      facilityId,
      customerId: globalFilters.customerId,
      carrierId: globalFilters.carrierId,
      appointmentType: globalFilters.appointmentType,
      dateFrom: comparisonRange?.dateFrom,
      dateTo: comparisonRange?.dateTo,
    },
    globalFilters.compareMode !== "off",
  );

  const {
    data: intelligenceData,
    loading: intelligenceLoading,
    error: intelligenceError,
  } = useDashboardIntelligence(intelligenceFilters);

  const isDashboardLoading =
    dashboardLoading && !dashboard;

  const {
    simulation: dashboardSimulation,
    loading: dashboardSimulationLoading,
    error: dashboardSimulationError,
    run: runDashboardSimulation,
    reset: resetDashboardSimulation,
  } = useDashboardWhatIf();

  function runWhatIfScenario(request: {
    extra_loaders: number;
    extra_forklifts: number;
    pre_stage_products: boolean;
  }) {
    setDashboardWhatIfRequest(request);

    void runDashboardSimulation({
      ...request,
      facility_id: facilityId,
      customer_id: globalFilters.customerId,
      carrier_id: globalFilters.carrierId,
      appointment_type: globalFilters.appointmentType,
      date_from: activeDateRange.dateFrom,
      date_to: activeDateRange.dateTo,
    });
  }

  function resetWhatIfScenario() {
    setDashboardWhatIfRequest(null);
    resetDashboardSimulation();
  }

  useEffect(() => {
    if (filterOptionsLoading) return;
    onAvailableFacilitiesChange?.(filterOptions.facilities);
  }, [filterOptions.facilities, filterOptionsLoading, onAvailableFacilitiesChange]);

  useEffect(() => {
    if (filterOptionsLoading) return;

    setGlobalFilters((current) => {
      let changed = false;
      const next = { ...current };

      if (
        current.customerId &&
        !filterOptions.customers.some((item) => item.id === current.customerId)
      ) {
        next.customerId = undefined;
        changed = true;
      }
      if (
        current.carrierId &&
        !filterOptions.carriers.some((item) => item.id === current.carrierId)
      ) {
        next.carrierId = undefined;
        changed = true;
      }
      if (
        current.appointmentType &&
        !filterOptions.appointmentTypes.some((item) => item.id === current.appointmentType)
      ) {
        next.appointmentType = undefined;
        changed = true;
      }

      return changed ? next : current;
    });
  }, [filterOptions, filterOptionsLoading]);

  useEffect(() => {
    setIntelligenceFilters((current) => ({
      ...current,
      facilityId,
    }));
  }, [facilityId]);

  useEffect(() => {
    if (intelligenceFilterOptionsLoading) return;

    setIntelligenceFilters((current) => {
      let changed = false;
      const next = { ...current };

      if (
        current.customerId &&
        !intelligenceFilterOptions.customers.some(
          (item) => item.id === current.customerId,
        )
      ) {
        next.customerId = undefined;
        changed = true;
      }

      if (
        current.carrierId &&
        !intelligenceFilterOptions.carriers.some(
          (item) => item.id === current.carrierId,
        )
      ) {
        next.carrierId = undefined;
        changed = true;
      }

      if (
        current.appointmentType &&
        !intelligenceFilterOptions.appointmentTypes.some(
          (item) => item.id === current.appointmentType,
        )
      ) {
        next.appointmentType = undefined;
        changed = true;
      }

      return changed ? next : current;
    });
  }, [intelligenceFilterOptions, intelligenceFilterOptionsLoading]);

  useEffect(() => {
    setAppointmentFilters((current) => ({
      ...current,
      facilityId,
      customerId: globalFilters.customerId,
      carrierId: globalFilters.carrierId,
      appointmentType: globalFilters.appointmentType,
      dateFrom: activeDateRange.dateFrom,
      dateTo: activeDateRange.dateTo,
    }));
    resetDashboardSimulation();
  }, [
    facilityId,
    globalFilters.customerId,
    globalFilters.carrierId,
    globalFilters.appointmentType,
    globalFilters.datePreset,
    globalFilters.customDate,
    globalFilters.customDateEnd,
  ]);

  const displayedDashboard =
    dashboard && dashboardSimulation
      ? {
        ...dashboard,
        summary: {
          ...dashboard.summary,
          ...dashboardSimulation.dashboard_patch.summary,
        },
        late_appointment_outcomes:
          dashboardSimulation.dashboard_patch
            .late_appointment_outcomes,
        risk_distribution:
          dashboardSimulation.dashboard_patch
            .risk_distribution,
        recommendation_savings:
          dashboardSimulation.dashboard_patch
            .recommendation_savings,
      }
      : dashboard;

  function openTabAndScroll(
    tab: OperationsTab,
    selector: string,
  ) {
    setActiveTab(tab);
    window.setTimeout(() => {
      document.querySelector(selector)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 60);
  }

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

    openTabAndScroll(
      "operations",
      ".appointment-operations-full",
    );
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
    setAppointmentFilters({
      facilityId,
      customerId: globalFilters.customerId,
      carrierId: globalFilters.carrierId,
      appointmentType: globalFilters.appointmentType,
      dateFrom: activeDateRange.dateFrom,
      dateTo: activeDateRange.dateTo,
    });
  }

  function refreshOperationsData() {
    refreshAppointmentDetails();
    refreshAppointments();
    refreshDashboard();
    resetDashboardSimulation();
  }

  function handleKpiDrillDown(key: string) {
    setActiveTab("operations");

    if (key === "appointments") {
      clearAppointmentFilters();
    } else if (key === "sla_misses") {
      setAppointmentFilters((current) => ({
        ...current,
        outcome: "Missed SLA",
        riskLevel: undefined,
      }));
    } else if (key === "recovered_by_actions") {
      setAppointmentFilters((current) => ({
        ...current,
        outcome: "Recovered with recommendations",
        riskLevel: undefined,
      }));
    } else if (key === "late_turns_recovered") {
      setAppointmentFilters((current) => ({
        ...current,
        outcome: "Recovered with recommendations",
        riskLevel: undefined,
      }));
    } else if (key === "late_arrivals") {
      setAppointmentFilters((current) => ({
        ...current,
        riskLevel: "High",
        outcome: undefined,
      }));
    }

    document.querySelector(".appointment-operations-full")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  const dashboardKpis = [
    {
      label: "Appointments",
      value: isDashboardLoading
        ? "…"
        : displayedDashboard
          ? displayedDashboard.summary.total_appointments.toLocaleString()
          : "—",
      detail: "Current demo operations",
    },
    {
      label: "Late Arrivals",
      value: isDashboardLoading
        ? "…"
        : displayedDashboard
          ? displayedDashboard.summary.late_arrivals.toLocaleString()
          : "—",
      detail: "Arrived after scheduled time",
    },
    {
      label: "SLA Misses",
      value: isDashboardLoading
        ? "…"
        : displayedDashboard
          ? displayedDashboard.summary.sla_misses.toLocaleString()
          : "—",
      detail: "Completed beyond SLA",
    },
    {
      label: "Late Turns Recovered",
      value: isDashboardLoading
        ? "…"
        : displayedDashboard
          ? displayedDashboard.summary.late_turned_on_time.toLocaleString()
          : "—",
      detail: "Late arrivals turned on time",
    },
    {
      label: "Recovered by Actions",
      value: isDashboardLoading
        ? "…"
        : displayedDashboard
          ? displayedDashboard.summary
            .late_recovered_with_recommendations
            .toLocaleString()
          : "—",
      detail: displayedDashboard
        ? `${displayedDashboard.summary.recovery_contribution_percent}% of recoveries`
        : "Recommendation contribution",
    },
  ];

  return (
    <>
      <Header
        notification={
          displayedDashboard ? (
            <OperationalAlertsPanel
              alerts={displayedDashboard.operational_alerts ?? []}
              onFilterQueue={(riskLevel) => {
                setAppointmentFilters((current) => ({
                  ...current,
                  riskLevel,
                  outcome: undefined,
                }));
                openTabAndScroll("operations", ".appointment-operations-full");
              }}
              onOpenAppointment={(appointmentId) => {
                const existing = appointments.find(
                  (appointment) => appointment.appt_id === appointmentId,
                );
                setSelectedAppointment(
                  existing ?? createAppointmentPlaceholder(appointmentId),
                );
              }}
              onRunWhatIf={() => {
                runWhatIfScenario({
                  extra_loaders: 1,
                  extra_forklifts: 1,
                  pre_stage_products: false,
                });
                openTabAndScroll("predictions", ".live-what-if-panel");
              }}
            />
          ) : undefined
        }
      >
        <OperationsFilterBar
          filters={globalFilters}
          customers={availableCustomers}
          carriers={availableCarriers}
          appointmentTypes={availableAppointmentTypes}
          onChange={(nextFilters) => {
            setGlobalFilters(nextFilters);
            resetDashboardSimulation();
          }}
          currentDashboard={
            globalFilters.compareMode === "previous-week"
              ? currentWeekDashboard
              : dashboard
          }
          comparisonDashboard={comparisonDashboard}
          comparisonLoading={comparisonLoading || currentWeekLoading}
        />
      </Header>

      <div className="operations-page-flow">
        <nav className="operations-page-tabs" role="tablist" aria-label="Operations workspace">
          {([
            ["operations", "Operations"],
            ["recommendations", "Recommendations and Intelligence"],
            ["predictions", "Predictions"],
            ["docks", "Docks"],
          ] as const).map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              className={activeTab === tab ? "active" : ""}
              onClick={() => setActiveTab(tab)}
            >
              {label}
            </button>
          ))}
        </nav>

        {dashboardError && (
          <div className="table-error">
            {dashboardError}
          </div>
        )}

        {activeTab === "operations" && (
          <div className="operations-tab-panel" role="tabpanel">
            <SectionHeading
              eyebrow="Live operations"
              title="Operational health"
              description="A focused view of appointment flow, SLA exposure and recovery performance."
            />

            <section className="kpi-grid intelligent-kpi-grid">
              {displayedDashboard?.intelligent_kpis?.length
                ? displayedDashboard.intelligent_kpis.map((kpi, index) => (
                  <IntelligentKpiCard
                    key={kpi.key}
                    kpi={kpi}
                    index={index}
                    expanded={kpiCardsExpanded}
                    onToggleExpanded={() =>
                      setKpiCardsExpanded((current) => !current)
                    }
                    onDrillDown={handleKpiDrillDown}
                    averageLabel={
                      globalFilters.datePreset === "custom"
                        ? "Average"
                        : "7-day avg"
                    }
                  />
                ))
                : dashboardKpis.map((kpi, index) => (
                  <KpiCard
                    key={kpi.label}
                    index={index}
                    label={kpi.label}
                    value={kpi.value}
                    detail={kpi.detail}
                  />
                ))}
            </section>

            <SectionHeading
              eyebrow="Performance signals"
              title="Outcome and risk intelligence"
              description="Select a chart segment to focus the live appointment queue."
            />

            {displayedDashboard && (
              <div className="outcome-feed-layout">
                <div className="outcome-feed-charts">
                  <DashboardCharts
                    lateOutcomes={displayedDashboard.late_appointment_outcomes}
                    riskDistribution={displayedDashboard.risk_distribution}
                    selectedRiskLevel={appointmentFilters.riskLevel}
                    selectedOutcome={appointmentFilters.outcome}
                    onRiskSelect={handleRiskSelect}
                    onOutcomeSelect={handleOutcomeSelect}
                  />
                </div>

                <AiOperationsFeed
                  items={displayedDashboard.operations_feed ?? []}
                  onOpenAppointment={(appointmentId) => {
                    const existing = appointments.find(
                      (appointment) => appointment.appt_id === appointmentId,
                    );
                    setSelectedAppointment(
                      existing ?? createAppointmentPlaceholder(appointmentId),
                    );
                  }}
                  onFilterQueue={(riskLevel) => {
                    setAppointmentFilters((current) => ({
                      ...current,
                      riskLevel,
                      outcome: undefined,
                    }));
                    openTabAndScroll("operations", ".appointment-operations-full");
                  }}
                  onRunWhatIf={() => {
                    runWhatIfScenario({
                      extra_loaders: 1,
                      extra_forklifts: 1,
                      pre_stage_products: true,
                    });
                    openTabAndScroll("predictions", ".live-what-if-panel");
                  }}
                />
              </div>
            )}

            {(
              appointmentFilters.dockId ||
              appointmentFilters.riskLevel ||
              appointmentFilters.outcome
            ) && (
                <div className="active-filter-banner">
                  <div>
                    <strong>Appointment filter:</strong>{" "}
                    {appointmentFilters.dockId
                      ? `Dock ${appointmentFilters.dockId.split("-D").pop()}`
                      : appointmentFilters.riskLevel
                        ? `${appointmentFilters.riskLevel} risk`
                        : appointmentFilters.outcome}
                  </div>

                  <button
                    type="button"
                    onClick={clearAppointmentFilters}
                  >
                    Clear filter
                  </button>
                </div>
              )}

            <SectionHeading
              eyebrow="Execution workspace"
              title="Live appointment operations"
              description="Review the queue and open appointment intelligence for detailed recovery decisions."
            />

            <section className="appointment-operations-full">
              <AppointmentTable
                appointments={appointments}
                pagination={pagination}
                pageSize={pageSize}
                sortBy={sortBy}
                sortDirection={sortDirection}
                loading={loading}
                error={error}
                onPreviousPage={goToPreviousPage}
                onNextPage={goToNextPage}
                onPageSizeChange={changePageSize}
                onSortChange={changeSort}
                onCreateAppointment={() => setCreateAppointmentOpen(true)}
                onAppointmentSelect={setSelectedAppointment}
                selectedAppointmentId={selectedAppointment?.appt_id}
              />
            </section>
          </div>
        )}

        {activeTab === "recommendations" && (
          <div className="operations-tab-panel" role="tabpanel">
            <section className={`ai-workspace-shell ${aiWorkspaceExpanded ? "expanded" : "collapsed"}`}>
              <div className="ai-workspace-toolbar">
                <div>
                  <span className="panel-eyebrow">AI decision workspace</span>
                  <strong>AI Mission Center & Interactive AI Actions</strong>
                </div>

                <button
                  type="button"
                  className="ai-workspace-toggle"
                  onClick={() => setAiWorkspaceExpanded((current) => !current)}
                  aria-expanded={aiWorkspaceExpanded}
                >
                  {aiWorkspaceExpanded ? "Collapse" : "Expand"}
                  <b aria-hidden="true">{aiWorkspaceExpanded ? "−" : "+"}</b>
                </button>
              </div>

              {aiWorkspaceExpanded && (
                <div className="recommendations-action-row">
                  {displayedDashboard && (
                    <AiMissionCenter
                      missions={displayedDashboard.ai_missions ?? []}
                      onFilterQueue={(riskLevel) => {
                        setAppointmentFilters((current) => ({
                          ...current,
                          riskLevel,
                          outcome: undefined,
                        }));
                        openTabAndScroll("operations", ".appointment-operations-full");
                      }}
                      onOpenAppointment={(appointmentId) => {
                        const existing = appointments.find(
                          (appointment) => appointment.appt_id === appointmentId,
                        );
                        setSelectedAppointment(
                          existing ?? createAppointmentPlaceholder(appointmentId),
                        );
                      }}
                      onRunWhatIf={() => {
                        runWhatIfScenario({
                          extra_loaders: 1,
                          extra_forklifts: 1,
                          pre_stage_products: true,
                        });
                        openTabAndScroll("predictions", ".live-what-if-panel");
                      }}
                    />
                  )}

                  {displayedDashboard && (
                    <AiActionCardsPanel
                      missions={displayedDashboard.ai_missions ?? []}
                      alerts={displayedDashboard.operational_alerts ?? []}
                      predictiveTimeline={displayedDashboard.predictive_timeline ?? null}
                      onOpenAppointment={(appointmentId) => {
                        const existing = appointments.find(
                          (appointment) => appointment.appt_id === appointmentId,
                        );
                        setSelectedAppointment(
                          existing ?? createAppointmentPlaceholder(appointmentId),
                        );
                      }}
                      onFilterQueue={(riskLevel) => {
                        setAppointmentFilters((current) => ({
                          ...current,
                          riskLevel,
                          outcome: undefined,
                        }));
                        openTabAndScroll("operations", ".appointment-operations-full");
                      }}
                      onRunWhatIf={() => {
                        runWhatIfScenario({
                          extra_loaders: 1,
                          extra_forklifts: 1,
                          pre_stage_products: true,
                        });
                        openTabAndScroll("predictions", ".live-what-if-panel");
                      }}
                      onForecast={() => {
                        document.querySelector(".predictive-timeline-panel")?.scrollIntoView({
                          behavior: "smooth",
                          block: "start",
                        });
                      }}
                      onCompare={(riskLevel) => {
                        setAppointmentFilters((current) => ({
                          ...current,
                          riskLevel,
                          outcome: undefined,
                        }));

                        openTabAndScroll(
                          "operations",
                          ".outcome-feed-layout",
                        );
                      }}
                    />
                  )}

                </div>
              )}
            </section>

            <RootCauseIntelligenceSection
              filters={intelligenceFilters}
              referenceData={intelligenceReferenceData}
              delayReasons={intelligenceData?.delay_sla_reasons ?? []}
              recoveryPlans={intelligenceData?.recovery_plan_performance ?? []}
              loading={intelligenceLoading}
              error={intelligenceError}
              onChange={setIntelligenceFilters}
            />

            {displayedDashboard?.predictive_timeline && (
              <PredictiveTimeline
                data={displayedDashboard.predictive_timeline}
                onOpenAppointment={(appointmentId) => {
                  const existing = appointments.find(
                    (appointment) => appointment.appt_id === appointmentId,
                  );
                  setSelectedAppointment(
                    existing ?? createAppointmentPlaceholder(appointmentId),
                  );
                }}
                onRunWhatIf={() => {
                  runWhatIfScenario({
                    extra_loaders: 1,
                    extra_forklifts: 1,
                    pre_stage_products: true,
                  });
                  openTabAndScroll("predictions", ".live-what-if-panel");
                }}
              />
            )}
          </div>
        )}

        {activeTab === "predictions" && (
          <div className="operations-tab-panel" role="tabpanel">
            {displayedDashboard && (
              <>
                <SectionHeading
                  eyebrow="Business impact"
                  title="Recommendation Savings Comparison"
                  description="Measure the financial value of accepted recovery recommendations."
                />

                <RecommendationSavings
                  savings={displayedDashboard.recommendation_savings}
                />
              </>
            )}

            <div className="dashboard-collapsible-stack">
              <CollapsibleDashboardSection
                eyebrow="Executive intelligence"
                title="Watch Operating Conditions"
                description="Monitor live warehouse health, critical appointments and the operational priorities leadership needs to know."
                status={
                  displayedDashboard?.executive_intelligence
                    ? displayedDashboard.executive_intelligence.health_status
                    : dashboardLoading
                      ? "Loading"
                      : undefined
                }
                summary={
                  displayedDashboard?.executive_intelligence
                    ? `${displayedDashboard.executive_intelligence.headline_metrics.critical_appointments} critical appointments · ${displayedDashboard.executive_intelligence.headline_metrics.predicted_sla_misses} predicted SLA misses`
                    : "Executive conditions and priority signals"
                }
              >
                <ExecutiveOperationsCenter
                  dashboard={displayedDashboard}
                  loading={dashboardLoading}
                  onShowCritical={() => handleRiskSelect("Critical")}
                  onOpenAppointment={(appointmentId) => {
                    const existing = appointments.find(
                      (appointment) => appointment.appt_id === appointmentId,
                    );

                    setSelectedAppointment(
                      existing ?? createAppointmentPlaceholder(appointmentId),
                    );
                  }}
                />
              </CollapsibleDashboardSection>

              <CollapsibleDashboardSection
                eyebrow="Predictive intelligence"
                title="AI Prediction Center"
                description="Review forward-looking SLA, congestion, detention and recovery forecasts generated from the latest ML scores."
                status={dashboardSimulation ? "Scenario forecast" : "Live forecast"}
                summary={
                  displayedDashboard?.prediction_center
                    ? `${displayedDashboard.prediction_center.risk_matrix
                      .find((row) => row.risk_level === "Critical")
                      ?.appointment_count ?? 0} critical-risk appointments · ${displayedDashboard.prediction_center.forecast_window_minutes}-minute horizon`
                    : "Machine-learning forecasts and confidence signals"
                }
              >
                {displayedDashboard?.prediction_center ? (
                  <PredictionCenter
                    data={displayedDashboard.prediction_center}
                    selectedRiskLevel={appointmentFilters.riskLevel}
                    onRiskSelect={handleRiskSelect}
                    simulationActive={Boolean(dashboardSimulation)}
                  />
                ) : (
                  <div className="dashboard-collapsible-empty">
                    {dashboardLoading
                      ? "Loading prediction intelligence…"
                      : "Prediction intelligence is currently unavailable."}
                  </div>
                )}
              </CollapsibleDashboardSection>

              <CollapsibleDashboardSection
                eyebrow="ML governance"
                title="ML Model Health & Retraining"
                description="Monitor production accuracy, data drift, optimizer effectiveness and retraining signals."
                status="Production monitoring"
                summary="Accuracy · drift · retraining governance"
              >
                <MLModelHealth
                  facilityId={facilityId}
                />
              </CollapsibleDashboardSection>

              <CollapsibleDashboardSection
                eyebrow="Scenario intelligence"
                title="Live What-If Simulation"
                description="Test labor, equipment and product-staging changes before execution. Simulation state is preserved while this panel is closed."
                status={dashboardSimulation ? "Simulation active" : "Ready"}
                summary={
                  dashboardSimulation
                    ? "Projected KPI, risk and savings values are active"
                    : "No scenario running · live baseline remains unchanged"
                }
              >
                <LiveWhatIfDashboard
                  simulation={dashboardSimulation}
                  loading={dashboardSimulationLoading}
                  error={dashboardSimulationError}
                  initialRequest={dashboardWhatIfRequest}
                  onRun={runWhatIfScenario}
                  onReset={resetWhatIfScenario}
                />

                {dashboardSimulation && (
                  <div className="simulation-active-banner">
                    <div>
                      <span className="simulation-banner-icon">◇</span>
                      <div>
                        <strong>Simulation view is active</strong>
                        <span>KPI cards, outcome charts, risk distribution and savings now show projected values.</span>
                      </div>
                    </div>
                    <button type="button" onClick={resetWhatIfScenario}>Return to live baseline</button>
                  </div>
                )}
              </CollapsibleDashboardSection>
            </div>
          </div>
        )}

        {activeTab === "docks" && (
          <div className="operations-tab-panel" role="tabpanel">
            <section className="panel capacity-overview-panel">
              <div className="panel-header capacity-overview-header">
                <div>
                  <span className="panel-eyebrow">Capacity overview</span>
                  <h2>
                    {capacityView === "dock-utilization"
                      ? "Dock Utilization"
                      : "Warehouse Risk Heat Map"}
                  </h2>
                  <p>
                    {capacityView === "dock-utilization"
                      ? "Track dock pressure and available capacity across the selected facility scope."
                      : "See dock pressure, congestion, SLA exposure and recovery opportunity in one view."}
                  </p>
                </div>

                <div
                  className="table-segmented-control capacity-view-control"
                  role="group"
                  aria-label="Capacity overview view"
                >
                  <button
                    type="button"
                    className={capacityView === "dock-utilization" ? "active" : ""}
                    onClick={() => setCapacityView("dock-utilization")}
                  >
                    Dock Utilization
                  </button>
                  <button
                    type="button"
                    className={capacityView === "risk-heatmap" ? "active" : ""}
                    onClick={() => setCapacityView("risk-heatmap")}
                  >
                    Risk Heat Map
                  </button>
                </div>
              </div>

              <div className="capacity-overview-view">
                {capacityView === "dock-utilization" && (
                  <DockUtilization
                    embedded
                    docks={[...(displayedDashboard?.warehouse_heatmap?.docks ?? [])]
                      .sort((left, right) =>
                        right.utilization_percent - left.utilization_percent ||
                        right.risk_score - left.risk_score
                      )
                      .slice(0, facilityId ? undefined : 10)
                      .map((dock) => ({
                        id: dock.dock_id,
                        name: dock.dock_name,
                        facilityName: dock.facility_name,
                        utilization: dock.utilization_percent,
                        status:
                          dock.health === "Critical" || dock.health === "High"
                            ? "Needs attention"
                            : dock.health === "Watch"
                              ? "Busy"
                              : dock.active
                                ? "Available"
                                : "Inactive",
                      }))}
                    showFacilityNames={!facilityId}
                  />
                )}

                {capacityView === "risk-heatmap" && displayedDashboard?.warehouse_heatmap && (
                  <WarehouseRiskHeatMap
                    embedded
                    limitToTopTen={!facilityId}
                    data={displayedDashboard.warehouse_heatmap}
                    onOpenAppointment={(appointmentId) => {
                      const existing = appointments.find(
                        (appointment) => appointment.appt_id === appointmentId,
                      );
                      setSelectedAppointment(
                        existing ?? createAppointmentPlaceholder(appointmentId),
                      );
                    }}
                    onFilterDock={(dockId) => {
                      setAppointmentFilters((current) => ({
                        ...current,
                        dockId,
                        riskLevel: undefined,
                        outcome: undefined,
                      }));

                      openTabAndScroll(
                        "operations",
                        ".appointment-operations-full",
                      );
                    }}
                    onRunWhatIf={() => {
                      runWhatIfScenario({
                        extra_loaders: 1,
                        extra_forklifts: 1,
                        pre_stage_products: true,
                      });
                      openTabAndScroll("predictions", ".live-what-if-panel");
                    }}
                  />
                )}
              </div>
            </section>
          </div>
        )}

        <GlobalWarehouseCopilot
          dashboard={displayedDashboard}
          loading={dashboardLoading}
          activeFilters={appointmentFilters}
          onApplyFilters={setAppointmentFilters}
          onClearFilters={clearAppointmentFilters}
          onOpenAppointment={(appointmentId) => {
            const existing = appointments.find(
              (appointment) => appointment.appt_id === appointmentId,
            );

            setSelectedAppointment(
              existing ?? createAppointmentPlaceholder(appointmentId),
            );
          }}
          onRunWhatIf={(request) => {
            runWhatIfScenario(request);
            openTabAndScroll("predictions", ".live-what-if-panel");
          }}
          onAppointmentCreated={async (result: CreateAppointmentResponse) => {
            refreshAppointments();
            refreshDashboard();
            setSelectedAppointment(createAppointmentPlaceholder(result.appt_id));
          }}
        />
      </div>

      <CreateAppointmentDrawer
        open={createAppointmentOpen}
        onClose={() => setCreateAppointmentOpen(false)}
        onCreated={async (result: CreateAppointmentResponse) => {
          refreshAppointments();
          refreshDashboard();
          setSelectedAppointment(createAppointmentPlaceholder(result.appt_id));
        }}
      />

      <AppointmentDetailsDrawer
        selectedAppointment={selectedAppointment}
        details={appointmentDetails}
        loading={appointmentDetailsLoading}
        error={appointmentDetailsError}
        onRefresh={refreshOperationsData}
        onClose={() => setSelectedAppointment(null)}
      />
    </>
  );
}

function createAppointmentPlaceholder(
  appointmentId: string,
): AppointmentListItem {
  return {
    appt_id: appointmentId,
    customer_name: null,
    customer_id: null,
    facility_id: "",
    facility_name: "Loading appointment…",
    carrier_id: null,
    carrier_name: null,
    scheduled_time: new Date().toISOString(),
    estimated_arrival_time: null,
    actual_arrival_time: null,
    assigned_dock_id: null,
    dock_name: null,
    status: "Loading",
    pallet_count: 0,
    sku_count: 0,
    priority: 0,
    sla_minutes: 120,
    actual_arrival_delay_minutes: null,
    predicted_duration_minutes: null,
    turn_risk_score: null,
    sla_recovery_probability: null,
    predicted_missed: null,
    recommended_action: null,
    estimated_savings: null,
  };
}

export default OperationsPage;

function getLastMonthRange() {
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 30);
  return {
    dateFrom: toLocalDate(start),
    dateTo: toLocalDate(end),
  };
}

function toLocalDate(value: Date) {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}