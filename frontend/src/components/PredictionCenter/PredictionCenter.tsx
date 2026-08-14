import type {
  PredictionCenterData,
  PredictionItem,
  PredictionTrend,
  RiskMatrixItem,
} from "../../types/dashboard";

interface PredictionCenterProps {
  data: PredictionCenterData;
  onRiskSelect: (riskLevel: string) => void;
  selectedRiskLevel?: string;
  simulationActive?: boolean;
}

const trendSymbol: Record<PredictionTrend, string> = {
  up: "↑",
  down: "↓",
  stable: "→",
};

function PredictionCard({ item }: { item: PredictionItem }) {
  return (
    <article className={`prediction-card prediction-tone-${item.tone}`}>
      <div className="prediction-card-topline">
        <span>{item.label}</span>
        <span className={`prediction-trend prediction-trend-${item.trend}`}>
          {trendSymbol[item.trend]}
        </span>
      </div>

      <div className="prediction-value-row">
        <strong>{item.value}</strong>
        <span>{item.unit}</span>
      </div>

      <div className="prediction-confidence">
        <div>
          <span>Confidence</span>
          <strong>{item.confidence}%</strong>
        </div>
        <div className="prediction-confidence-track" aria-hidden="true">
          <span style={{ width: `${item.confidence}%` }} />
        </div>
      </div>

      <dl className="prediction-context">
        <div>
          <dt>Primary factor</dt>
          <dd>{item.primary_factor}</dd>
        </div>
        <div>
          <dt>AI mitigation</dt>
          <dd>{item.recommendation}</dd>
        </div>
      </dl>
    </article>
  );
}

function RiskMatrix({
  rows,
  selectedRiskLevel,
  onRiskSelect,
}: {
  rows: RiskMatrixItem[];
  selectedRiskLevel?: string;
  onRiskSelect: (riskLevel: string) => void;
}) {
  return (
    <div className="prediction-risk-panel">
      <div className="prediction-subheading">
        <div>
          <span>Operational matrix</span>
          <h3>Portfolio risk</h3>
        </div>
        <small>Select a row to filter the appointment queue.</small>
      </div>

      <div className="prediction-risk-table-wrapper">
        <table className="prediction-risk-table">
          <thead>
            <tr>
              <th>Risk</th>
              <th>Appointments</th>
              <th>Trend</th>
              <th>AI recommendation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const selected = selectedRiskLevel === row.risk_level;
              return (
                <tr
                  key={row.risk_level}
                  className={selected ? "is-selected" : undefined}
                  onClick={() => onRiskSelect(row.risk_level)}
                >
                  <td>
                    <span className={`prediction-risk-chip risk-${row.risk_level.toLowerCase()}`}>
                      {row.risk_level}
                    </span>
                  </td>
                  <td><strong>{row.appointment_count}</strong></td>
                  <td>
                    <span className={`prediction-trend prediction-trend-${row.trend}`}>
                      {trendSymbol[row.trend]}
                    </span>
                  </td>
                  <td>{row.recommendation}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PredictionHistory({ data }: { data: PredictionCenterData }) {
  const maxValue = Math.max(
    1,
    ...data.history.flatMap((row) => [
      row.predicted_sla_misses,
      row.actual_sla_misses ?? 0,
    ]),
  );

  return (
    <div className="prediction-history-panel">
      <div className="prediction-subheading">
        <div>
          <span>Forecast history</span>
          <h3>Predicted versus actual</h3>
        </div>
        <div className="prediction-history-legend">
          <span><i className="legend-predicted" /> Predicted</span>
          <span><i className="legend-actual" /> Actual</span>
        </div>
      </div>

      <div className="prediction-history-bars">
        {data.history.map((row) => {
          const timestamp = new Date(row.timestamp);
          return (
            <div className="prediction-history-column" key={row.timestamp}>
              <div className="prediction-history-bar-area">
                <div
                  className="prediction-history-bar predicted"
                  title={`Predicted: ${row.predicted_sla_misses}`}
                  style={{ height: `${Math.max(8, row.predicted_sla_misses / maxValue * 100)}%` }}
                />
                <div
                  className="prediction-history-bar actual"
                  title={row.actual_sla_misses == null ? "Actual: pending" : `Actual: ${row.actual_sla_misses}`}
                  style={{ height: row.actual_sla_misses == null ? "4px" : `${Math.max(8, row.actual_sla_misses / maxValue * 100)}%` }}
                />
              </div>
              <strong>{timestamp.toLocaleTimeString([], { hour: "numeric" })}</strong>
              <span>{row.actual_sla_misses == null ? "Pending" : `${row.actual_sla_misses} actual`}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PredictionCenter({
  data,
  onRiskSelect,
  selectedRiskLevel,
  simulationActive = false,
}: PredictionCenterProps) {
  return (
    <section className="prediction-center" id="prediction-center">
      <header className="prediction-center-header">
        <div>
          <span className="prediction-center-eyebrow">Predictive operations</span>
          <h2>AI Prediction Center</h2>
          <p>{data.narrative}</p>
        </div>
        <div className="prediction-window-badge">
          <span className="prediction-live-dot" />
          {simulationActive ? "Scenario forecast" : `Next ${data.forecast_window_minutes} minutes`}
        </div>
      </header>

      <div className="prediction-grid">
        {data.predictions.map((item) => (
          <PredictionCard key={item.key} item={item} />
        ))}
      </div>

      <div className="prediction-lower-grid">
        <RiskMatrix
          rows={data.risk_matrix}
          selectedRiskLevel={selectedRiskLevel}
          onRiskSelect={onRiskSelect}
        />
        <PredictionHistory data={data} />
      </div>
    </section>
  );
}
