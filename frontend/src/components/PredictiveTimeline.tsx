import { useMemo, useState } from "react";

import type { PredictiveTimelineData, PredictiveTimelineEvent } from "../types/dashboard";

type Props = {
  data: PredictiveTimelineData;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
};

type Filter = "All" | "Critical" | "SLA Risk" | "Congestion" | "Detention";

export function PredictiveTimeline({
  data,
  onOpenAppointment,
  onRunWhatIf,
}: Props) {
  const [filter, setFilter] = useState<Filter>("All");
  const [selectedId, setSelectedId] = useState<string | null>(
    data.events[0]?.event_id ?? null,
  );

  const events = useMemo(() => {
    if (filter === "All") return data.events;
    if (filter === "Critical") {
      return data.events.filter((event) => event.severity === "Critical");
    }
    if (filter === "SLA Risk") {
      return data.events.filter((event) => event.event_type === "SLA_RISK_WINDOW");
    }
    if (filter === "Congestion") {
      return data.events.filter((event) => event.event_type === "DOCK_CONGESTION");
    }
    return data.events.filter((event) => event.event_type === "DETENTION_EXPOSURE");
  }, [data.events, filter]);

  const selected =
    events.find((event) => event.event_id === selectedId) ?? events[0] ?? null;

  return (
    <section className="panel predictive-timeline-panel">
      <div className="predictive-timeline-header">
        <div>
          <span className="panel-eyebrow">Forward-looking operations intelligence</span>
          <h2>Predictive Timeline</h2>
          <p>
            Forecasted SLA risk, congestion, detention and appointment surges over the
            next {data.horizon_hours} hours.
          </p>
        </div>

        <div className="predictive-timeline-summary">
          <span><strong>{data.summary.forecast_events}</strong> events</span>
          <span className="critical"><strong>{data.summary.critical_events}</strong> critical</span>
          <span><strong>{formatCurrency(data.summary.detention_exposure)}</strong> exposure</span>
        </div>
      </div>

      <div className="predictive-timeline-filters" role="group" aria-label="Predictive timeline filters">
        {(["All", "Critical", "SLA Risk", "Congestion", "Detention"] as Filter[]).map((option) => (
          <button
            key={option}
            type="button"
            className={filter === option ? "active" : ""}
            onClick={() => setFilter(option)}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="predictive-timeline-layout">
        <div className="predictive-timeline-track">
          <div className="predictive-now-line">
            <span>Now</span>
          </div>

          {events.map((event) => (
            <button
              key={event.event_id}
              type="button"
              className={`predictive-event ${event.severity.toLowerCase()} ${
                selected?.event_id === event.event_id ? "selected" : ""
              }`}
              onClick={() => setSelectedId(event.event_id)}
            >
              <time>{formatTime(event.forecast_time)}</time>
              <span className="predictive-event-node" aria-hidden="true" />
              <div className="predictive-event-copy">
                <div>
                  <span className={`predictive-severity ${event.severity.toLowerCase()}`}>
                    {event.severity}
                  </span>
                  <span className="predictive-event-type">
                    {humanize(event.event_type)}
                  </span>
                </div>
                <strong>{event.title}</strong>
                <small>{event.description}</small>
              </div>
              <span className="predictive-confidence">{event.confidence}% confidence</span>
            </button>
          ))}

          {events.length === 0 && (
            <div className="predictive-timeline-empty">
              <strong>No forecast events match this view</strong>
              <span>The next operating window currently has no qualifying risk signal.</span>
            </div>
          )}
        </div>

        <div className="predictive-timeline-detail">
          {selected ? (
            <TimelineDetail
              event={selected}
              onOpenAppointment={onOpenAppointment}
              onRunWhatIf={onRunWhatIf}
            />
          ) : (
            <div className="predictive-timeline-empty">
              <strong>No predicted disruption</strong>
              <span>Current forecast conditions are within configured thresholds.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function TimelineDetail({
  event,
  onOpenAppointment,
  onRunWhatIf,
}: {
  event: PredictiveTimelineEvent;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
}) {
  return (
    <>
      <div className="predictive-detail-topline">
        <span className={`predictive-severity ${event.severity.toLowerCase()}`}>
          {event.severity}
        </span>
        <time>{formatTime(event.forecast_time)}</time>
      </div>

      <h3>{event.title}</h3>
      <p>{event.description}</p>

      <div className="predictive-detail-metrics">
        <div><span>Impacted</span><strong>{event.impacted_appointment_count}</strong></div>
        <div><span>Confidence</span><strong>{event.confidence}%</strong></div>
        <div><span>Priority</span><strong>{event.priority_score}</strong></div>
        <div><span>Exposure</span><strong>{formatCurrency(event.detention_exposure)}</strong></div>
      </div>

      {(event.facility_name || event.dock_name) && (
        <div className="predictive-detail-location">
          {event.facility_name && <span>{event.facility_name}</span>}
          {event.dock_name && <strong>{event.dock_name}</strong>}
        </div>
      )}

      <div className="predictive-recommendation">
        <span>AI recommended intervention</span>
        <strong>{event.recommended_action}</strong>
      </div>

      <div className="predictive-detail-actions">
        {event.primary_appointment_id && (
          <button
            type="button"
            className="primary"
            onClick={() => onOpenAppointment(event.primary_appointment_id!)}
          >
            Open highest-risk appointment
          </button>
        )}
        <button type="button" onClick={onRunWhatIf}>Run What-If</button>
      </div>
    </>
  );
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

function humanize(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
