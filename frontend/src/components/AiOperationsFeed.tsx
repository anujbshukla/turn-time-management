import { useMemo, useState } from "react";

import type {
  OperationsFeedCategory,
  OperationsFeedItem,
} from "../types/dashboard";

type Props = {
  items: OperationsFeedItem[];
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
  onFilterQueue: (riskLevel?: string) => void;
};

const FILTERS: Array<"All" | OperationsFeedCategory> = [
  "All",
  "AI Decisions",
  "Operational Changes",
  "Appointments",
  "Alerts",
  "Missions",
];

export function AiOperationsFeed({
  items,
  onOpenAppointment,
  onRunWhatIf,
  onFilterQueue,
}: Props) {
  const [filter, setFilter] = useState<"All" | OperationsFeedCategory>("All");
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);

  const filteredItems = useMemo(
    () =>
      filter === "All"
        ? items
        : items.filter((item) => item.category === filter),
    [filter, items],
  );

  const visibleItems = filteredItems.slice(0, 18);

  function runPrimaryAction(item: OperationsFeedItem) {
    if (item.appointment_id) {
      onOpenAppointment(item.appointment_id);
      return;
    }

    if (item.action === "run_what_if") {
      onRunWhatIf();
      return;
    }

    if (item.severity === "Critical" || item.severity === "High") {
      onFilterQueue(item.severity);
    }
  }

  return (
    <aside className="panel ai-operations-feed">
      <div className="ai-operations-feed-header">
        <div>
          <span className="panel-eyebrow">Live activity intelligence</span>
          <h2>AI Operations Feed</h2>
          <p>Appointments, AI decisions, alerts and operational changes.</p>
        </div>
        <span className="ai-feed-live-status">
          <i aria-hidden="true" />
          Live
        </span>
      </div>

      <div className="ai-feed-filters" role="group" aria-label="Filter activity feed">
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            className={filter === option ? "active" : ""}
            onClick={() => setFilter(option)}
          >
            {option === "Operational Changes" ? "Changes" : option}
          </button>
        ))}
      </div>

      <div className="ai-feed-list">
        {visibleItems.map((item) => {
          const expanded = expandedItemId === item.feed_id;

          return (
            <article
              key={item.feed_id}
              className={`ai-feed-item ${item.category
                .toLowerCase()
                .replaceAll(" ", "-")} ${item.severity.toLowerCase()}`}
            >
              <div className="ai-feed-timeline-column" aria-hidden="true">
                <span className="ai-feed-marker">{eventSymbol(item)}</span>
                <i />
              </div>

              <div className="ai-feed-item-content">
                <div className="ai-feed-item-heading">
                  <div>
                    <span className="ai-feed-category">{item.category}</span>
                    <h3>{item.title}</h3>
                  </div>
                  <time>{formatRelativeTime(item.occurred_at)}</time>
                </div>

                <p>{item.description}</p>

                <div className="ai-feed-meta">
                  {item.facility_name && <span>{item.facility_name}</span>}
                  {item.actor && <span>{item.actor}</span>}
                  <span className={`ai-feed-severity ${item.severity.toLowerCase()}`}>
                    {item.severity}
                  </span>
                </div>

                {expanded && (
                  <div className="ai-feed-details">
                    {item.old_value !== null && (
                      <div>
                        <span>Previous</span>
                        <strong>{item.old_value}</strong>
                      </div>
                    )}
                    {item.new_value !== null && (
                      <div>
                        <span>Updated</span>
                        <strong>{item.new_value}</strong>
                      </div>
                    )}
                    {Object.entries(item.details ?? {})
                      .slice(0, 4)
                      .map(([key, value]) => (
                        <div key={key}>
                          <span>{key.replaceAll("_", " ")}</span>
                          <strong>{formatDetail(value)}</strong>
                        </div>
                      ))}
                  </div>
                )}

                <div className="ai-feed-actions">
                  {(item.appointment_id || item.action !== "none") && (
                    <button type="button" onClick={() => runPrimaryAction(item)}>
                      {item.appointment_id
                        ? "Open appointment"
                        : item.action === "run_what_if"
                          ? "Run What-If"
                          : "View queue"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="quiet"
                    onClick={() =>
                      setExpandedItemId(expanded ? null : item.feed_id)
                    }
                  >
                    {expanded ? "Hide details" : "Explain"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}

        {visibleItems.length === 0 && (
          <div className="ai-feed-empty">
            <strong>No activity in this view</strong>
            <span>Choose another filter or wait for the next 30-second refresh.</span>
          </div>
        )}
      </div>

      <div className="ai-feed-footer">
        <span>Auto-refreshes every 30 seconds</span>
        <strong>{items.length} recent events</strong>
      </div>
    </aside>
  );
}

function eventSymbol(item: OperationsFeedItem) {
  if (item.category === "AI Decisions") return "AI";
  if (item.category === "Alerts") return "!";
  if (item.category === "Missions") return "M";
  if (item.category === "Operational Changes") return "↺";
  return "•";
}

function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));

  if (minutes < 1) return "Now";
  if (minutes === 1) return "1 min";
  if (minutes < 60) return `${minutes} min`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr`;

  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatDetail(value: unknown) {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value ?? "—");
}
