import { useState } from "react";

export type AiActionCardMetric = {
  label: string;
  value: string;
};

export type AiActionCardAction = {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "quiet";
  disabled?: boolean;
};

type Props = {
  source: "Mission" | "Alert" | "Forecast";
  severity: "Info" | "Warning" | "High" | "Critical";
  title: string;
  summary: string;
  recommendation?: string | null;
  metrics?: AiActionCardMetric[];
  actions: AiActionCardAction[];
  explanation?: string | null;
  confidence?: number | null;
};

export function AiActionCard({
  source,
  severity,
  title,
  summary,
  recommendation,
  metrics = [],
  actions,
  explanation,
  confidence,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className={`ai-action-card ${severity.toLowerCase()}`}>
      <div className="ai-action-card-topline">
        <div className="ai-action-card-badges">
          <span className={`ai-action-severity ${severity.toLowerCase()}`}>
            {severity}
          </span>
          <span className="ai-action-source">{source}</span>
        </div>

        {confidence !== null && confidence !== undefined && (
          <span className="ai-action-confidence">{Math.round(confidence)}% confidence</span>
        )}
      </div>

      <h3>{title}</h3>
      <p>{summary}</p>

      {metrics.length > 0 && (
        <div className="ai-action-metrics">
          {metrics.slice(0, 3).map((metric) => (
            <div key={`${metric.label}-${metric.value}`}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
      )}

      {recommendation && (
        <div className="ai-action-recommendation">
          <span>AI recommended action</span>
          <strong>{recommendation}</strong>
        </div>
      )}

      {expanded && explanation && (
        <div className="ai-action-explanation">
          <span>Why this matters</span>
          <p>{explanation}</p>
        </div>
      )}

      <div className="ai-action-card-actions">
        {actions.map((action) => (
          <button
            key={action.label}
            type="button"
            className={action.variant ?? "secondary"}
            onClick={action.onClick}
            disabled={action.disabled}
          >
            {action.label}
          </button>
        ))}

        {explanation && (
          <button
            type="button"
            className="quiet"
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Hide explanation" : "Explain"}
          </button>
        )}
      </div>
    </article>
  );
}
