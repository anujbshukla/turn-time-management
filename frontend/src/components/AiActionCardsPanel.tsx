import { useMemo } from "react";

import { AiActionCard } from "./AiActionCard";

import type {
  AiMission,
  OperationalAlert,
  PredictiveTimelineData,
} from "../types/dashboard";

type Props = {
  missions: AiMission[];
  alerts: OperationalAlert[];
  predictiveTimeline?: PredictiveTimelineData | null;
  onOpenAppointment: (appointmentId: string) => void;
  onFilterQueue: (riskLevel?: string) => void;
  onRunWhatIf: () => void;
  onForecast: () => void;
  onCompare: (riskLevel?: string) => void;
};

type Candidate = {
  id: string;
  source: "Mission" | "Alert" | "Forecast";
  severity: "Info" | "Warning" | "High" | "Critical";
  score: number;
  title: string;
  summary: string;
  recommendation?: string | null;
  appointmentId?: string | null;
  riskLevel?: string | null;
  confidence?: number | null;
  explanation: string;
  metrics: Array<{ label: string; value: string }>;
};

export function AiActionCardsPanel({
  missions,
  alerts,
  predictiveTimeline,
  onOpenAppointment,
  onFilterQueue,
  onRunWhatIf,
  onForecast,
  onCompare,
}: Props) {
  const cards = useMemo(() => {
    const candidates: Candidate[] = [];

    missions
      .filter((mission) => mission.status !== "Completed" && mission.status !== "Dismissed")
      .forEach((mission) => {
        candidates.push({
          id: `mission-${mission.mission_id}`,
          source: "Mission",
          severity: mission.severity,
          score: mission.priority_score + severityBoost(mission.severity),
          title: mission.title,
          summary: mission.objective,
          recommendation: mission.recommended_actions?.[0] ?? null,
          appointmentId: mission.primary_appointment_id,
          riskLevel:
            mission.severity === "Critical" || mission.severity === "High"
              ? mission.severity
              : null,
          confidence: mission.recovery_probability,
          explanation:
            `${mission.impacted_appointment_count} appointment(s) are tied to this mission. ` +
            `The mission projects ${Math.round(mission.projected_minutes_saved)} minutes saved ` +
            `and ${formatCurrency(mission.estimated_financial_benefit)} in operational value.`,
          metrics: [
            {
              label: "Impacted",
              value: mission.impacted_appointment_count.toLocaleString(),
            },
            {
              label: "Minutes saved",
              value: Math.round(mission.projected_minutes_saved).toLocaleString(),
            },
            {
              label: "Projected value",
              value: formatCurrency(mission.estimated_financial_benefit),
            },
          ],
        });
      });

    alerts.forEach((alert) => {
      candidates.push({
        id: `alert-${alert.alert_id}`,
        source: "Alert",
        severity: alert.severity,
        score:
          severityBoost(alert.severity) +
          Math.min(alert.impacted_appointment_count * 3, 30) +
          Math.min(alert.estimated_financial_exposure / 100, 30),
        title: alert.title,
        summary: alert.description,
        recommendation: alert.recommended_action,
        appointmentId: alert.highest_priority_appointment_id,
        riskLevel: alert.risk_level,
        confidence: null,
        explanation:
          `${alert.impacted_appointment_count} appointment(s) are affected. ` +
          `Estimated financial exposure is ${formatCurrency(
            alert.estimated_financial_exposure,
          )}.`,
        metrics: [
          {
            label: "Impacted",
            value: alert.impacted_appointment_count.toLocaleString(),
          },
          {
            label: "Exposure",
            value: formatCurrency(alert.estimated_financial_exposure),
          },
          {
            label: "Category",
            value: alert.category,
          },
        ],
      });
    });

    predictiveTimeline?.events.slice(0, 6).forEach((event) => {
      candidates.push({
        id: `forecast-${event.event_id}`,
        source: "Forecast",
        severity: event.severity,
        score: event.priority_score + severityBoost(event.severity),
        title: event.title,
        summary: event.description,
        recommendation: event.recommended_action,
        appointmentId: event.primary_appointment_id,
        riskLevel:
          event.severity === "Critical" || event.severity === "High"
            ? event.severity
            : null,
        confidence: event.confidence,
        explanation:
          `This condition is forecast for ${formatTime(event.forecast_time)}. ` +
          `${event.impacted_appointment_count} appointment(s) may be affected with ` +
          `${formatCurrency(event.detention_exposure)} in projected detention exposure.`,
        metrics: [
          {
            label: "Forecast time",
            value: formatTime(event.forecast_time),
          },
          {
            label: "Impacted",
            value: event.impacted_appointment_count.toLocaleString(),
          },
          {
            label: "Exposure",
            value: formatCurrency(event.detention_exposure),
          },
        ],
      });
    });

    return candidates
      .sort((left, right) => right.score - left.score)
      .filter(
        (candidate, index, array) =>
          array.findIndex(
            (other) =>
              other.title.toLowerCase() === candidate.title.toLowerCase() &&
              other.source === candidate.source,
          ) === index,
      )
      .slice(0, 3);
  }, [alerts, missions, predictiveTimeline]);

  return (
    <section className="panel ai-action-cards-section mission-style-actions">
      <div className="ai-action-cards-header mission-style-actions-header">
        <div className="ai-mission-title-group">
          <span className="ai-mission-mark" aria-hidden="true">AI</span>
          <div>
            <span className="panel-eyebrow">Decision acceleration</span>
            <h2>Interactive AI Actions</h2>
          </div>
        </div>

        <div className="ai-mission-summary">
          <span><strong>{cards.length}</strong> priorities</span>
        </div>
      </div>

      <div className="ai-action-cards-body">
        <p className="ai-action-cards-description">
          Highest-priority missions, alerts and forecast signals translated into executable warehouse actions.
        </p>

        <div className="ai-action-cards-grid">
          {cards.length === 0 ? (
            <div className="ai-action-empty">
              <span className="ai-mission-mark" aria-hidden="true">AI</span>
              <strong>No active AI priorities</strong>
              <p>
                New mission, alert and forecast recommendations will appear here
                as operating conditions change.
              </p>
            </div>
          ) : cards.map((card) => {
            const actions = [];

            if (card.appointmentId) {
              actions.push({
                label: "Open",
                variant: "primary" as const,
                onClick: () => onOpenAppointment(card.appointmentId!),
              });
            }

            if (card.riskLevel) {
              actions.push({
                label: "View queue",
                onClick: () => onFilterQueue(card.riskLevel ?? undefined),
              });
            }

            if (card.source === "Forecast") {
              actions.push({
                label: "Forecast",
                onClick: onForecast,
              });
            } else {
              actions.push({
                label: "Compare",
                onClick: () => onCompare(card.riskLevel ?? undefined),
              });
            }

            actions.push({
              label: "Optimize",
              onClick: onRunWhatIf,
            });

            return (
              <AiActionCard
                key={card.id}
                source={card.source}
                severity={card.severity}
                title={card.title}
                summary={card.summary}
                recommendation={card.recommendation}
                metrics={card.metrics}
                confidence={card.confidence}
                explanation={card.explanation}
                actions={actions}
              />
            );
          })}
        </div>
      </div>
    </section>
  );
}

function severityBoost(severity: Candidate["severity"]) {
  if (severity === "Critical") return 100;
  if (severity === "High") return 70;
  if (severity === "Warning") return 35;
  return 10;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}
