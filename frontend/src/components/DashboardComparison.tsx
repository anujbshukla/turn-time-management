import type { DashboardResponse } from "../types/dashboard";
import type { ComparisonMode } from "../types/appointments";

interface Props {
  current: DashboardResponse;
  previous: DashboardResponse;
  mode: ComparisonMode;
  currentRange: string;
  previousRange: string;
}

export function DashboardComparison({ current, previous, mode, currentRange, previousRange }: Props) {
  const metrics = [
    ["Appointments", current.summary.total_appointments, previous.summary.total_appointments, false],
    ["Late arrivals", current.summary.late_arrivals, previous.summary.late_arrivals, true],
    ["SLA misses", current.summary.sla_misses, previous.summary.sla_misses, true],
    ["Late turns recovered", current.summary.late_turned_on_time, previous.summary.late_turned_on_time, false],
    ["Recovered by actions", current.summary.late_recovered_with_recommendations, previous.summary.late_recovered_with_recommendations, false],
  ] as const;

  return (
    <section className="comparison-panel panel">
      <div className="comparison-panel-header">
        <div><span className="comparison-eyebrow">Comparison active</span><h2>{mode === "week-over-week" ? "Week-over-week performance" : "Performance vs last week"}</h2></div>
        <div className="comparison-periods"><span><i className="period-dot current" />{currentRange}</span><span><i className="period-dot previous" />{previousRange}</span></div>
      </div>
      <div className="comparison-metric-grid">
        {metrics.map(([label, currentValue, previousValue, lowerIsBetter]) => {
          const delta = Number(currentValue) - Number(previousValue);
          const pct = Number(previousValue) === 0 ? null : (delta / Number(previousValue)) * 100;
          const favorable = delta === 0 ? null : lowerIsBetter ? delta < 0 : delta > 0;
          return <div className="comparison-metric" key={label}>
            <span>{label}</span><strong>{Number(currentValue).toLocaleString()}</strong>
            <div className="comparison-baseline">Last week <b>{Number(previousValue).toLocaleString()}</b></div>
            <small className={favorable === null ? "neutral" : favorable ? "positive" : "negative"}>{delta > 0 ? "+" : ""}{delta.toLocaleString()} {pct === null ? "" : `(${pct > 0 ? "+" : ""}${pct.toFixed(1)}%)`}</small>
          </div>;
        })}
      </div>
    </section>
  );
}
