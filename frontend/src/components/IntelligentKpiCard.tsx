import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";

import type { IntelligentKpi } from "../types/dashboard";

type Props = {
  kpi: IntelligentKpi;
  index: number;
  expanded: boolean;
  onToggleExpanded: () => void;
  onDrillDown?: (key: string) => void;
  averageLabel?: string;
};

export function IntelligentKpiCard({
  kpi,
  index,
  expanded,
  onToggleExpanded,
  onDrillDown,
  averageLabel = "7-day avg",
}: Props) {
  const [explanationOpen, setExplanationOpen] = useState(false);
  const trendData = kpi.trend.map((value, point) => ({
    point,
    value,
    date: kpi.trend_dates?.[point] ?? "",
  }));
  const targetProgress = kpi.target == null
    ? null
    : Math.min(100, Math.max(0, kpi.target === 0
      ? (kpi.value === 0 ? 100 : 0)
      : (kpi.value / kpi.target) * 100));

  return (
    <article
      className={`kpi-card intelligent-kpi-card ${kpi.tone} ${expanded ? "expanded" : "collapsed"}`}
      onClick={() => onDrillDown?.(kpi.key)}
      role={onDrillDown ? "button" : undefined}
      tabIndex={onDrillDown ? 0 : undefined}
      onKeyDown={(event) => {
        if (onDrillDown && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onDrillDown(kpi.key);
        }
      }}
    >
      <div className="kpi-card-topline">
        <span>{kpi.label}</span>
        <div className="kpi-card-heading-actions">
          <span className="kpi-card-index" aria-hidden="true">
            {String(index + 1).padStart(2, "0")}
          </span>
          <button
            type="button"
            className="kpi-card-expand-button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${kpi.label}`}
            onClick={(event) => {
              event.stopPropagation();

              if (expanded) {
                setExplanationOpen(false);
              }

              onToggleExpanded();
            }}
          >
            <span aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
          </button>
        </div>
      </div>

      <div className="intelligent-kpi-value-row">
        <strong>{formatValue(kpi.value, kpi.format)}</strong>
        {expanded && (
          <span className={`intelligent-kpi-delta ${kpi.tone}`}>
            <span aria-hidden="true">{directionIcon(kpi.direction)}</span>
            {Math.abs(kpi.delta_percent).toFixed(1)}%
          </span>
        )}
      </div>

      {expanded && (
        <div className="intelligent-kpi-expanded-content">
          <small>{kpi.detail}</small>

          <div className="intelligent-kpi-sparkline" aria-label={`${kpi.label} 14-day trend`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <Tooltip
                  contentStyle={{ fontSize: 10, borderRadius: 8 }}
                  formatter={(value) => [
                    formatValue(Number(value), kpi.format),
                    kpi.label,
                  ]}
                  labelFormatter={(_, payload) => {
                    const rawDate = payload?.[0]?.payload?.date;
                    if (!rawDate) return "";
                    return new Intl.DateTimeFormat(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    }).format(new Date(`${rawDate}T00:00:00`));
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="currentColor"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="intelligent-kpi-comparison">
            <span>Yesterday <strong>{formatValue(kpi.previous_value, kpi.format)}</strong></span>
            <span>{averageLabel} <strong>{formatValue(kpi.rolling_average, kpi.format)}</strong></span>
          </div>

          {targetProgress !== null && (
            <div className="intelligent-kpi-target">
              <div>
                <span>Target</span>
                <strong>{formatValue(kpi.target ?? 0, kpi.format)}</strong>
              </div>
              <div className="intelligent-kpi-target-track" aria-hidden="true">
                <span style={{ width: `${targetProgress}%` }} />
              </div>
            </div>
          )}

          <div className="intelligent-kpi-footer">
            <span>Forecast {formatValue(kpi.forecast, kpi.format)} · {kpi.forecast_confidence}% confidence</span>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setExplanationOpen((current) => !current);
              }}
            >
              {explanationOpen ? "Hide why" : "Why?"}
            </button>
          </div>

          {explanationOpen && (
            <div className="intelligent-kpi-explanation" onClick={(event) => event.stopPropagation()}>
              <strong>AI performance note</strong>
              <p>{kpi.explanation}</p>
            </div>
          )}
        </div>
      )}

      <div className="kpi-card-accent" aria-hidden="true" />
    </article>
  );
}

function formatValue(value: number, format: IntelligentKpi["format"]) {
  if (format === "currency") {
    return new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", maximumFractionDigits: 0,
    }).format(value);
  }
  if (format === "percent") return `${Math.round(value)}%`;
  return Math.round(value).toLocaleString();
}

function directionIcon(direction: IntelligentKpi["direction"]) {
  if (direction === "up") return "↑";
  if (direction === "down") return "↓";
  return "→";
}
