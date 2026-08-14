import type { DashboardResponse } from "../types/dashboard";

interface ExecutiveOperationsCenterProps {
  dashboard: DashboardResponse | null;
  loading: boolean;
  onShowCritical: () => void;
  onOpenAppointment: (appointmentId: string) => void;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function ExecutiveOperationsCenter({
  dashboard,
  loading,
  onShowCritical,
  onOpenAppointment,
}: ExecutiveOperationsCenterProps) {
  const intelligence = dashboard?.executive_intelligence;

  if (loading && !intelligence) {
    return (
      <section className="executive-center executive-center-loading" aria-busy="true">
        <div className="executive-loading-line" />
        <div className="executive-loading-grid">
          <div />
          <div />
          <div />
        </div>
      </section>
    );
  }

  if (!intelligence) {
    return null;
  }

  const scoreStyle = {
    "--health-score": `${intelligence.health_score * 3.6}deg`,
  } as React.CSSProperties;

  return (
    <section className={`executive-center tone-${intelligence.health_tone}`}>
      <div className="operations-status-banner">
        <div className="operations-status-copy">
          <span className="operations-live-dot" aria-hidden="true" />
          <div>
            <span className="operations-status-label">Live operations status</span>
            <strong>{intelligence.health_status} operating conditions</strong>
          </div>
        </div>
        <div className="operations-status-metrics">
          <span>{intelligence.headline_metrics.critical_appointments} critical</span>
          <span>{intelligence.headline_metrics.predicted_sla_misses} predicted misses</span>
          <span>{formatCurrency(intelligence.headline_metrics.net_ai_savings)} AI value</span>
        </div>
      </div>

      <div className="executive-center-grid">
        <article className="executive-briefing-card">
          <div className="executive-card-heading">
            <div>
              <span className="executive-eyebrow">AI executive briefing</span>
              <h2>What leadership needs to know now</h2>
            </div>
            <span className="executive-ai-chip">AI grounded</span>
          </div>

          <p className="executive-briefing-text">{intelligence.briefing}</p>

          <div className="executive-headline-grid">
            <div>
              <span>Critical appointments</span>
              <strong>{intelligence.headline_metrics.critical_appointments}</strong>
            </div>
            <div>
              <span>Predicted SLA misses</span>
              <strong>{intelligence.headline_metrics.predicted_sla_misses}</strong>
            </div>
            <div>
              <span>Net AI savings</span>
              <strong>{formatCurrency(intelligence.headline_metrics.net_ai_savings)}</strong>
            </div>
            <div>
              <span>Detention exposure</span>
              <strong>{formatCurrency(intelligence.headline_metrics.detention_exposure)}</strong>
            </div>
          </div>

          <button type="button" className="executive-primary-action" onClick={onShowCritical}>
            Focus critical appointments
          </button>
        </article>

        <article className="health-score-card">
          <div className="executive-card-heading compact">
            <div>
              <span className="executive-eyebrow">Warehouse health</span>
              <h2>Composite operating score</h2>
            </div>
          </div>

          <div className="health-score-body">
            <div className="health-score-ring" style={scoreStyle}>
              <div>
                <strong>{intelligence.health_score}</strong>
                <span>/ 100</span>
              </div>
            </div>
            <div className="health-score-summary">
              <strong>{intelligence.health_status}</strong>
              <span>Weighted across service, recovery, risk and AI effectiveness.</span>
            </div>
          </div>

          <div className="health-indicator-list">
            {intelligence.indicators.map((indicator) => (
              <div key={indicator.label} className="health-indicator-row">
                <div>
                  <span>{indicator.label}</span>
                  <strong>{indicator.score}</strong>
                </div>
                <div className="health-indicator-track">
                  <span style={{ width: `${Math.max(0, Math.min(100, indicator.score))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="top-priorities-card">
          <div className="executive-card-heading compact">
            <div>
              <span className="executive-eyebrow">Top priorities</span>
              <h2>Immediate operational focus</h2>
            </div>
          </div>

          <div className="top-priority-list">
            {intelligence.top_priorities.length === 0 ? (
              <div className="top-priority-empty">No immediate appointment escalation is required.</div>
            ) : (
              intelligence.top_priorities.map((priority, index) => (
                <button
                  type="button"
                  key={`${priority.appt_id ?? "priority"}-${index}`}
                  className="top-priority-item"
                  onClick={() => priority.appt_id && onOpenAppointment(priority.appt_id)}
                  disabled={!priority.appt_id}
                >
                  <span className={`priority-rank severity-${priority.severity.toLowerCase()}`}>
                    {index + 1}
                  </span>
                  <span className="priority-copy">
                    <span className="priority-meta">
                      <strong>{priority.appt_id ?? "Portfolio"}</strong>
                      <em>{priority.severity}</em>
                    </span>
                    <strong className="priority-title">{priority.title}</strong>
                    <span className="priority-reason">{priority.reason}</span>
                  </span>
                  <span className="priority-value">
                    <strong>{priority.risk_score.toFixed(0)}</strong>
                    <span>risk</span>
                    {priority.estimated_savings > 0 && (
                      <small>{formatCurrency(priority.estimated_savings)} value</small>
                    )}
                  </span>
                </button>
              ))
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
