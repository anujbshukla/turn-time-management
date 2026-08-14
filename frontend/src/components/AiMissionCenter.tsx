import { useEffect, useMemo, useState } from "react";

import type { AiMission } from "../types/dashboard";

type Props = {
  missions: AiMission[];
  onFilterQueue: (riskLevel?: string) => void;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
};

type MissionStatus = "Proposed" | "Accepted" | "Completed" | "Dismissed";

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
      mission.effectiveStatus === "Proposed" || mission.effectiveStatus === "Accepted",
  );
  const completedMissions = missionRows.filter(
    (mission) =>
      mission.effectiveStatus === "Completed" || mission.effectiveStatus === "Dismissed",
  );
  const visibleMissions = view === "active" ? activeMissions : completedMissions;
  const acceptedCount = activeMissions.filter(
    (mission) => mission.effectiveStatus === "Accepted",
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

                <div className="ai-mission-card-actions">
                  {mission.effectiveStatus === "Proposed" && (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => setMissionStatus(mission.mission_id, "Accepted")}
                    >
                      Accept mission
                    </button>
                  )}

                  {mission.effectiveStatus === "Accepted" && (
                    <button
                      type="button"
                      className="success"
                      onClick={() => setMissionStatus(mission.mission_id, "Completed")}
                    >
                      Complete
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

                  <button type="button" onClick={onRunWhatIf}>Run What-If</button>

                  {mission.effectiveStatus !== "Completed" &&
                    mission.effectiveStatus !== "Dismissed" && (
                      <button
                        type="button"
                        className="quiet"
                        onClick={() => setMissionStatus(mission.mission_id, "Dismissed")}
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
