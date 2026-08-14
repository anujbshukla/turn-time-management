import { useEffect, useMemo, useRef, useState } from "react";

import type { OperationalAlert } from "../types/dashboard";

type Props = {
  alerts: OperationalAlert[];
  onFilterQueue: (riskLevel?: string) => void;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
};

type AlertPreference = {
  status: "Dismissed" | "Snoozed";
  snoozedUntil?: string;
};

const STORAGE_KEY = "warehouse-operational-alert-preferences";

export function OperationalAlertsPanel({
  alerts,
  onFilterQueue,
  onOpenAppointment,
  onRunWhatIf,
}: Props) {
  const [preferences, setPreferences] = useState<Record<string, AlertPreference>>({});
  const [open, setOpen] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("All");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) setPreferences(JSON.parse(saved));
    } catch {
      setPreferences({});
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  function savePreferences(next: Record<string, AlertPreference>) {
    setPreferences(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  const activeAlerts = useMemo(() => {
    const now = Date.now();
    return alerts.filter((alert) => {
      const preference = preferences[alert.alert_id];
      if (preference?.status === "Dismissed") return false;
      if (
        preference?.status === "Snoozed" &&
        preference.snoozedUntil &&
        new Date(preference.snoozedUntil).getTime() > now
      ) {
        return false;
      }
      return true;
    });
  }, [alerts, preferences]);

  const filteredAlerts = useMemo(
    () =>
      activeAlerts.filter(
        (alert) => severityFilter === "All" || alert.severity === severityFilter,
      ),
    [activeAlerts, severityFilter],
  );

  function snoozeAlert(alertId: string) {
    savePreferences({
      ...preferences,
      [alertId]: {
        status: "Snoozed",
        snoozedUntil: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      },
    });
  }

  function dismissAlert(alertId: string) {
    savePreferences({
      ...preferences,
      [alertId]: { status: "Dismissed" },
    });
  }

  return (
    <div className="operational-alert-notification" ref={containerRef}>
      <button
        type="button"
        className="operational-alert-trigger"
        onClick={() => setOpen((current) => !current)}
        aria-label={`${activeAlerts.length} live operational alerts`}
        aria-expanded={open}
      >
        <span aria-hidden="true">!</span>
        <span className="operational-alert-count">{activeAlerts.length}</span>
      </button>

      {open && (
        <section className="operational-alert-popover" aria-label="Live Operational Alerts">
          <div className="operational-alert-popover-header">
            <div>
              <span className="panel-eyebrow">Notification center</span>
              <h2>Live Operational Alerts</h2>
            </div>
            <select
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
              aria-label="Filter operational alerts by severity"
            >
              <option>All</option>
              <option>Critical</option>
              <option>High</option>
              <option>Warning</option>
              <option>Info</option>
            </select>
          </div>

          <div className="operational-alert-popover-list">
            {filteredAlerts.map((alert) => (
              <article
                key={alert.alert_id}
                className={`notification-alert-card ${alert.severity.toLowerCase()}`}
              >
                <div className="notification-alert-heading">
                  <span className={`alert-severity ${alert.severity.toLowerCase()}`}>
                    {alert.severity}
                  </span>
                  <span className="alert-category">{alert.category}</span>
                  <time>{formatRelativeTime(alert.generated_at)}</time>
                </div>
                <h3>{alert.title}</h3>
                <p>{alert.recommended_action}</p>
                <div className="notification-alert-meta">
                  <span>{alert.impacted_appointment_count.toLocaleString()} impacted</span>
                  <span>{formatCurrency(alert.estimated_financial_exposure)} exposure</span>
                </div>
                <div className="notification-alert-actions">
                  {alert.risk_level && (
                    <button type="button" onClick={() => onFilterQueue(alert.risk_level ?? undefined)}>
                      View queue
                    </button>
                  )}
                  {alert.highest_priority_appointment_id && (
                    <button
                      type="button"
                      onClick={() => onOpenAppointment(alert.highest_priority_appointment_id!)}
                    >
                      Open
                    </button>
                  )}
                  <button type="button" onClick={onRunWhatIf}>What-If</button>
                  <button type="button" onClick={() => snoozeAlert(alert.alert_id)}>Snooze</button>
                  <button type="button" className="quiet" onClick={() => dismissAlert(alert.alert_id)}>
                    Dismiss
                  </button>
                </div>
              </article>
            ))}

            {filteredAlerts.length === 0 && (
              <div className="operational-alert-empty compact">
                <strong>No active alerts</strong>
                <span>There are no alerts matching this view.</span>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function formatCurrency(value: number | null | undefined) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "Now";
  const minutes = Math.round((timestamp - Date.now()) / 60000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  return formatter.format(Math.round(minutes / 60), "hour");
}
