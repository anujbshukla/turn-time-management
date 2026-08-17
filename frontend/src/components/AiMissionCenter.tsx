import { useEffect, useMemo, useState } from "react";

import type {
  AiMission,
  OptimizationMissionExecution,
  OptimizationMissionScenarioResponse,
  OptimizationScenarioConstraints,
} from "../types/dashboard";
import {
  acceptOptimizationMission,
  simulateOptimizationMission,
  refreshOptimizationMissionOutcomes,
  updateOptimizationMissionStatus,
} from "../services/optimization";

type Props = {
  missions: AiMission[];
  onFilterQueue: (riskLevel?: string) => void;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
};

type MissionStatus = "Proposed" | "Accepted" | "In Progress" | "Completed" | "Dismissed";

type MissionPreference = {
  status: MissionStatus;
  updatedAt: string;
};

const STORAGE_KEY = "warehouse-ai-mission-preferences";

export function AiMissionCenter({
  missions,
  onFilterQueue,
  onOpenAppointment,
  onRunWhatIf,
}: Props) {
  const [view, setView] = useState<"active" | "completed">("active");
  const [preferences, setPreferences] = useState<Record<string, MissionPreference>>({});
  const [executions, setExecutions] = useState<
    Record<string, OptimizationMissionExecution>
  >({});
  const [pendingMissionId, setPendingMissionId] = useState<string | null>(null);
  const [missionError, setMissionError] = useState<string | null>(null);
  const [scenarioMissionId, setScenarioMissionId] = useState<string | null>(null);
  const [scenarioLoadingId, setScenarioLoadingId] = useState<string | null>(null);
  const [scenarioResults, setScenarioResults] = useState<
    Record<string, OptimizationMissionScenarioResponse>
  >({});
  const [scenarioInputs, setScenarioInputs] = useState<
    Record<string, OptimizationScenarioConstraints>
  >({});

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) setPreferences(JSON.parse(saved));
    } catch {
      setPreferences({});
    }
  }, []);

  function setMissionStatus(missionId: string, status: MissionStatus) {
    const next = {
      ...preferences,
      [missionId]: {
        status,
        updatedAt: new Date().toISOString(),
      },
    };
    setPreferences(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function scenarioFor(mission: AiMission): OptimizationScenarioConstraints {
    return (
      scenarioInputs[mission.mission_id] ?? {
        max_extra_loaders_per_hour: null,
        max_extra_forklifts_per_hour: null,
        max_staging_labor_per_hour: null,
        allow_dock_reassignment: true,
      }
    );
  }

  function updateScenario(
    mission: AiMission,
    patch: Partial<OptimizationScenarioConstraints>,
  ) {
    setScenarioInputs((current) => ({
      ...current,
      [mission.mission_id]: {
        ...scenarioFor(mission),
        ...patch,
      },
    }));
  }

  async function runMissionScenario(mission: AiMission) {
    if (!mission.facility_id || !mission.window_start || !mission.window_end) {
      setMissionError("Mission operating-window context is incomplete.");
      return;
    }

    const scenario = scenarioFor(mission);
    setScenarioLoadingId(mission.mission_id);
    setMissionError(null);
    try {
      const result = await simulateOptimizationMission({
        facility_id: mission.facility_id,
        date_from: mission.window_start,
        date_to: mission.window_end,
        max_missions: 1,
        ...scenario,
      });
      setScenarioResults((current) => ({
        ...current,
        [mission.mission_id]: result,
      }));
    } catch (error) {
      setMissionError(
        error instanceof Error
          ? error.message
          : "Unable to re-optimize this mission.",
      );
    } finally {
      setScenarioLoadingId(null);
    }
  }

  async function acceptMission(mission: AiMission) {
    setPendingMissionId(mission.mission_id);
    setMissionError(null);
    try {
      const execution = await acceptOptimizationMission(
        mission,
        scenarioResults[mission.mission_id]
          ? scenarioFor(mission)
          : undefined,
      );
      setExecutions((current) => ({
        ...current,
        [mission.mission_id]: execution,
      }));
      setMissionStatus(mission.mission_id, "Accepted");
    } catch (error) {
      setMissionError(
        error instanceof Error
          ? error.message
          : "Unable to accept the coordinated mission.",
      );
    } finally {
      setPendingMissionId(null);
    }
  }

  async function transitionMission(
    mission: AiMission,
    status: "In Progress" | "Completed" | "Dismissed",
  ) {
    const execution = executions[mission.mission_id];
    const databaseMissionId =
      execution?.database_mission_id ??
      (typeof execution?.mission_id === "number"
        ? execution.mission_id
        : mission.database_mission_id);

    if (!databaseMissionId) {
      setMissionError(
        "Accept this mission before changing its execution status.",
      );
      return;
    }

    setPendingMissionId(mission.mission_id);
    setMissionError(null);
    try {
      const updated = await updateOptimizationMissionStatus(
        databaseMissionId,
        status,
      );
      setExecutions((current) => ({
        ...current,
        [mission.mission_id]: {
          ...execution,
          ...updated,
          database_mission_id: databaseMissionId,
        },
      }));
      setMissionStatus(mission.mission_id, status);
    } catch (error) {
      setMissionError(
        error instanceof Error
          ? error.message
          : "Unable to update mission status.",
      );
    } finally {
      setPendingMissionId(null);
    }
  }

  async function refreshMissionOutcomes(mission: AiMission) {
    const execution = executions[mission.mission_id];
    const databaseMissionId =
      execution?.database_mission_id ??
      (typeof execution?.mission_id === "number"
        ? execution.mission_id
        : mission.database_mission_id);

    if (!databaseMissionId) {
      setMissionError("This mission has not been persisted yet.");
      return;
    }

    setPendingMissionId(mission.mission_id);
    setMissionError(null);
    try {
      const updated = await refreshOptimizationMissionOutcomes(
        databaseMissionId,
      );
      setExecutions((current) => ({
        ...current,
        [mission.mission_id]: {
          ...execution,
          ...updated,
          database_mission_id: databaseMissionId,
        },
      }));
    } catch (error) {
      setMissionError(
        error instanceof Error
          ? error.message
          : "Unable to refresh realized mission outcomes.",
      );
    } finally {
      setPendingMissionId(null);
    }
  }


  const missionRows = useMemo(
    () =>
      missions.map((mission) => ({
        ...mission,
        effectiveStatus: preferences[mission.mission_id]?.status ?? mission.status,
      })),
    [missions, preferences],
  );

  const activeMissions = missionRows.filter(
    (mission) =>
      mission.effectiveStatus === "Proposed" ||
      mission.effectiveStatus === "Accepted" ||
      mission.effectiveStatus === "In Progress",
  );
  const completedMissions = missionRows.filter(
    (mission) =>
      mission.effectiveStatus === "Completed" || mission.effectiveStatus === "Dismissed",
  );
  const visibleMissions = view === "active" ? activeMissions : completedMissions;
  const acceptedCount = activeMissions.filter(
    (mission) =>
      mission.effectiveStatus === "Accepted" ||
      mission.effectiveStatus === "In Progress",
  ).length;
  const totalBenefit = activeMissions.reduce(
    (total, mission) => total + mission.estimated_financial_benefit,
    0,
  );

  return (
    <section className="panel ai-mission-center expanded">
      <div className="ai-mission-header">
        <div className="ai-mission-title-group">
          <span className="ai-mission-mark" aria-hidden="true">AI</span>
          <div>
            <span className="panel-eyebrow">Action orchestration</span>
            <h2>AI Mission Center</h2>
          </div>
        </div>

        <div className="ai-mission-summary">
          <span><strong>{activeMissions.length}</strong> active</span>
          <span><strong>{acceptedCount}</strong> accepted</span>
          <span><strong>{formatCurrency(totalBenefit)}</strong> projected value</span>
        </div>
      </div>

      <div className="ai-mission-body">
          {missionError && (
            <div className="table-error ai-mission-execution-error">
              {missionError}
            </div>
          )}

          <div className="ai-mission-tabs" role="tablist" aria-label="Mission status">
            <button
              type="button"
              className={view === "active" ? "active" : ""}
              onClick={() => setView("active")}
            >
              Active ({activeMissions.length})
            </button>
            <button
              type="button"
              className={view === "completed" ? "active" : ""}
              onClick={() => setView("completed")}
            >
              History ({completedMissions.length})
            </button>
          </div>

          <div className="ai-mission-list">
            {visibleMissions.map((mission, index) => (
              <article
                key={mission.mission_id}
                className={`ai-mission-card ${mission.severity.toLowerCase()} ${mission.effectiveStatus.toLowerCase()}`}
              >
                <div className="ai-mission-priority">
                  <span>#{index + 1}</span>
                  <strong>{mission.priority_score}</strong>
                  <small>priority</small>
                </div>

                <div className="ai-mission-content">
                  <div className="ai-mission-card-heading">
                    <div>
                      <div className="ai-mission-badges">
                        <span className={`mission-severity ${mission.severity.toLowerCase()}`}>
                          {mission.severity}
                        </span>
                        <span>{mission.category}</span>
                        <span className={`mission-status ${mission.effectiveStatus.toLowerCase()}`}>
                          {mission.effectiveStatus}
                        </span>
                      </div>
                      <h3>{mission.title}</h3>
                    </div>
                    <time>{formatRelativeTime(mission.generated_at)}</time>
                  </div>

                  <p>{mission.objective}</p>

                  <div className="ai-mission-metrics">
                    <div>
                      <span>Impacted</span>
                      <strong>{mission.impacted_appointment_count.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span>Minutes saved</span>
                      <strong>{Math.round(mission.projected_minutes_saved).toLocaleString()}</strong>
                    </div>
                    <div>
                      <span>Projected value</span>
                      <strong>{formatCurrency(mission.estimated_financial_benefit)}</strong>
                    </div>
                    <div>
                      <span>Recovery probability</span>
                      <strong>{Math.round(mission.recovery_probability)}%</strong>
                    </div>
                  </div>

                  <div className="ai-mission-actions-list">
                    {mission.recommended_actions.map((action) => (
                      <span key={action}>{action}</span>
                    ))}
                  </div>
                </div>

                {executions[mission.mission_id]?.appointment_plan?.length ? (
                  <div className="ai-mission-execution-plan">
                    <strong>Coordinated execution plan</strong>
                    {executions[mission.mission_id].appointment_plan!
                      .slice(0, 5)
                      .map((item) => (
                        <button
                          type="button"
                          key={item.appt_id}
                          onClick={() => onOpenAppointment(item.appt_id)}
                        >
                          <span>#{item.priority_order} · {item.appt_id}</span>
                          <b>
                            {Math.round(item.baseline_projected_turn_minutes)}
                            {" → "}
                            {Math.round(item.optimized_projected_turn_minutes)}
                            {" min"}
                          </b>
                          <small>
                            {item.actions.length
                              ? item.actions
                                  .map((action) =>
                                    action.action_code
                                      .replaceAll("_", " ")
                                      .toLowerCase(),
                                  )
                                  .join(" · ")
                              : "monitor"}
                          </small>
                        </button>
                      ))}
                  </div>
                ) : null}

                {scenarioMissionId === mission.mission_id &&
                  mission.category === "Coordinated Recovery" && (
                    <div className="mission-what-if-panel">
                      <div className="mission-what-if-heading">
                        <div>
                          <span>Mission-level What-If</span>
                          <strong>Re-optimize the entire appointment group</strong>
                        </div>
                        <small>
                          Limits are caps on real available headroom, not synthetic capacity.
                        </small>
                      </div>

                      <div className="mission-what-if-controls">
                        {([
                          [
                            "max_extra_loaders_per_hour",
                            "Extra loaders / hour",
                          ],
                          [
                            "max_extra_forklifts_per_hour",
                            "Extra forklifts / hour",
                          ],
                          [
                            "max_staging_labor_per_hour",
                            "Staging labor / hour",
                          ],
                        ] as const).map(([field, label]) => {
                          const value = scenarioFor(mission)[field];
                          return (
                            <label key={field}>
                              <span>{label}</span>
                              <div className="mission-scenario-stepper">
                                <button
                                  type="button"
                                  disabled={(value ?? 0) <= 0}
                                  onClick={() =>
                                    updateScenario(mission, {
                                      [field]: Math.max(
                                        0,
                                        (value ?? 0) - 1,
                                      ),
                                    })
                                  }
                                >
                                  −
                                </button>
                                <strong>
                                  {value === null ? "Auto" : value}
                                </strong>
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateScenario(mission, {
                                      [field]:
                                        value === null ? 1 : value + 1,
                                    })
                                  }
                                >
                                  +
                                </button>
                                <button
                                  type="button"
                                  className="quiet"
                                  onClick={() =>
                                    updateScenario(mission, {
                                      [field]: null,
                                    })
                                  }
                                >
                                  Auto
                                </button>
                              </div>
                            </label>
                          );
                        })}

                        <label className="mission-dock-toggle">
                          <input
                            type="checkbox"
                            checked={
                              scenarioFor(mission).allow_dock_reassignment
                            }
                            onChange={(event) =>
                              updateScenario(mission, {
                                allow_dock_reassignment:
                                  event.target.checked,
                              })
                            }
                          />
                          <span>Allow compatible dock reassignment</span>
                        </label>
                      </div>

                      <button
                        type="button"
                        className="primary"
                        disabled={
                          scenarioLoadingId === mission.mission_id
                        }
                        onClick={() => void runMissionScenario(mission)}
                      >
                        {scenarioLoadingId === mission.mission_id
                          ? "Re-optimizing..."
                          : "Re-optimize mission"}
                      </button>

                      {scenarioResults[mission.mission_id]?.missions[0] &&
                        (() => {
                          const scenarioMission =
                            scenarioResults[mission.mission_id].missions[0];
                          return (
                            <div className="mission-scenario-result">
                              <div>
                                <span>Projected SLA misses</span>
                                <strong>
                                  {mission.projected_sla_misses_before ?? 0}
                                  {" → "}
                                  {scenarioMission.projected_sla_misses_after ?? 0}
                                </strong>
                              </div>
                              <div>
                                <span>Appointments recovered</span>
                                <strong>
                                  {scenarioMission.appointments_recovered ?? 0}
                                </strong>
                              </div>
                              <div>
                                <span>Minutes saved</span>
                                <strong>
                                  {Math.round(
                                    scenarioMission.projected_minutes_saved,
                                  )}
                                </strong>
                              </div>
                              <div>
                                <span>Net savings</span>
                                <strong>
                                  {formatCurrency(
                                    scenarioMission.estimated_financial_benefit,
                                  )}
                                </strong>
                              </div>
                              <div>
                                <span>Dock moves</span>
                                <strong>
                                  {scenarioMission.dock_feasibility?.dock_moves ?? 0}
                                </strong>
                              </div>
                              <div>
                                <span>Unresolved shortages</span>
                                <strong>
                                  {scenarioMission.resource_shortages?.length ?? 0}
                                </strong>
                              </div>
                            </div>
                          );
                        })()}
                    </div>
                  )}


                {mission.effectiveStatus === "Completed" &&
                  (() => {
                    const execution = executions[mission.mission_id];
                    const sampleSize = execution?.outcome_sample_size ?? 0;
                    const projectedMisses =
                      execution?.projected_sla_misses_after ??
                      mission.projected_sla_misses_after ??
                      0;
                    const projectedSavings =
                      execution?.estimated_net_savings ??
                      mission.estimated_financial_benefit;
                    return (
                      <div className="mission-realized-panel">
                        <div className="mission-realized-heading">
                          <div>
                            <span>Execution learning</span>
                            <strong>Projected vs. realized outcome</strong>
                          </div>
                          <button
                            type="button"
                            className="quiet"
                            disabled={pendingMissionId === mission.mission_id}
                            onClick={() => void refreshMissionOutcomes(mission)}
                          >
                            Refresh actuals
                          </button>
                        </div>
                        {sampleSize > 0 ? (
                          <div className="mission-realized-grid">
                            <div>
                              <span>SLA misses</span>
                              <strong>
                                {projectedMisses} → {execution?.realized_sla_misses ?? "—"}
                              </strong>
                              <small>Projected → realized</small>
                            </div>
                            <div>
                              <span>Minutes saved</span>
                              <strong>
                                {Math.round(mission.projected_minutes_saved)} →{" "}
                                {Math.round(execution?.realized_minutes_saved ?? 0)}
                              </strong>
                              <small>Projected → realized</small>
                            </div>
                            <div>
                              <span>Net savings</span>
                              <strong>
                                {formatCurrency(projectedSavings)} →{" "}
                                {formatCurrency(execution?.realized_net_savings ?? 0)}
                              </strong>
                              <small>Projected → realized</small>
                            </div>
                            <div>
                              <span>Learning sample</span>
                              <strong>{sampleSize}</strong>
                              <small>Appointments with actual turn data</small>
                            </div>
                          </div>
                        ) : (
                          <p className="mission-realized-empty">
                            Mission execution is complete, but appointment actual turn
                            times are not available yet. Refresh after operational
                            actuals are posted.
                          </p>
                        )}
                      </div>
                    );
                  })()}

                <div className="ai-mission-card-actions">
                  {mission.effectiveStatus === "Proposed" && (
                    <button
                      type="button"
                      className="primary"
                      disabled={pendingMissionId === mission.mission_id}
                      onClick={() => void acceptMission(mission)}
                    >
                      {pendingMissionId === mission.mission_id
                        ? "Accepting..."
                        : "Accept mission"}
                    </button>
                  )}

                  {mission.effectiveStatus === "Accepted" && (
                    <button
                      type="button"
                      className="primary"
                      disabled={pendingMissionId === mission.mission_id}
                      onClick={() =>
                        void transitionMission(mission, "In Progress")
                      }
                    >
                      Start execution
                    </button>
                  )}

                  {mission.effectiveStatus === "In Progress" && (
                    <button
                      type="button"
                      className="success"
                      disabled={pendingMissionId === mission.mission_id}
                      onClick={() =>
                        void transitionMission(mission, "Completed")
                      }
                    >
                      Complete mission
                    </button>
                  )}

                  {mission.primary_appointment_id && (
                    <button
                      type="button"
                      onClick={() => onOpenAppointment(mission.primary_appointment_id!)}
                    >
                      Open appointment
                    </button>
                  )}

                  {mission.severity === "Critical" || mission.severity === "High" ? (
                    <button type="button" onClick={() => onFilterQueue(mission.severity)}>
                      View queue
                    </button>
                  ) : null}

                  {mission.category === "Coordinated Recovery" ? (
                    <button
                      type="button"
                      onClick={() =>
                        setScenarioMissionId((current) =>
                          current === mission.mission_id
                            ? null
                            : mission.mission_id,
                        )
                      }
                    >
                      Mission What-If
                    </button>
                  ) : (
                    <button type="button" onClick={onRunWhatIf}>
                      Run What-If
                    </button>
                  )}

                  {mission.effectiveStatus !== "Completed" &&
                    mission.effectiveStatus !== "Dismissed" && (
                      <button
                        type="button"
                        className="quiet"
                        disabled={pendingMissionId === mission.mission_id}
                        onClick={() => {
                          if (mission.effectiveStatus === "Proposed") {
                            setMissionStatus(
                              mission.mission_id,
                              "Dismissed",
                            );
                          } else {
                            void transitionMission(
                              mission,
                              "Dismissed",
                            );
                          }
                        }}
                      >
                        Dismiss
                      </button>
                    )}
                </div>
              </article>
            ))}

            {visibleMissions.length === 0 && (
              <div className="ai-mission-empty">
                <strong>No missions in this view</strong>
                <span>New missions will appear when operational conditions require action.</span>
              </div>
            )}
          </div>
      </div>
    </section>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatRelativeTime(value: string) {
  const elapsedMinutes = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 60000),
  );
  if (elapsedMinutes < 1) return "Just now";
  if (elapsedMinutes === 1) return "1 min ago";
  return `${elapsedMinutes} min ago`;
}
