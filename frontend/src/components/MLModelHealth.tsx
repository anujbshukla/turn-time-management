import { useEffect, useMemo, useState } from "react";

import { getMLMonitoring } from "../services/mlMonitoring";
import type { MLMonitoringData } from "../types/dashboard";

interface MLModelHealthProps {
  facilityId?: string;
}

function percent(value: number | null | undefined) {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function minutes(value: number | null | undefined) {
  if (value == null) return "—";
  return `${Number(value).toFixed(1)} min`;
}

export function MLModelHealth({
  facilityId,
}: MLModelHealthProps) {
  const [data, setData] = useState<MLMonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(persist = true) {
    setLoading(true);
    setError(null);
    try {
      const result = await getMLMonitoring(
        30,
        facilityId,
        persist,
      );
      setData(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load ML monitoring.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(false);
  }, [facilityId]);

  const topDrift = useMemo(
    () => data?.feature_drift.features.slice(0, 5) ?? [],
    [data],
  );

  if (loading && !data) {
    return (
      <section className="ml-health-panel">
        <div className="dashboard-collapsible-empty">
          Calculating model health…
        </div>
      </section>
    );
  }

  if (error && !data) {
    return (
      <section className="ml-health-panel">
        <div className="table-error">{error}</div>
      </section>
    );
  }

  if (!data) return null;

  return (
    <section className="ml-health-panel">
      <div className="ml-health-model-version">
        <div>
          <span>Production model</span>
          <strong>{data.model_version}</strong>
          <small>
            Last {data.window_days} days · accuracy, drift and optimizer outcomes
          </small>
        </div>

        <div className="ml-health-header-actions">
          <span
            className={`ml-health-status ml-health-status-${data.health_status
              .toLowerCase()
              .replaceAll(" ", "-")}`}
          >
            {data.health_status}
          </span>
          <button
            type="button"
            disabled={loading}
            onClick={() => void load(true)}
          >
            {loading ? "Refreshing…" : "Refresh monitoring"}
          </button>
        </div>
      </div>

      <div className="ml-health-metrics">
        <article>
          <span>Turn-duration MAE</span>
          <strong>{minutes(data.performance.duration_mae)}</strong>
          <small>{data.performance.sample_size} realized predictions</small>
        </article>
        <article>
          <span>SLA miss recall</span>
          <strong>{percent(data.performance.sla_recall)}</strong>
          <small>{data.performance.false_negative} false negatives</small>
        </article>
        <article>
          <span>SLA miss precision</span>
          <strong>{percent(data.performance.sla_precision)}</strong>
          <small>{data.performance.false_positive} false positives</small>
        </article>
        <article>
          <span>Feature drift</span>
          <strong>{data.feature_drift.score.toFixed(2)}</strong>
          <small>
            {data.feature_drift.score >= 1
              ? "High distribution shift"
              : data.feature_drift.score >= 0.5
                ? "Watch distribution shift"
                : "Stable operating mix"}
          </small>
        </article>
        <article>
          <span>Optimizer savings error</span>
          <strong>
            {data.optimizer_effectiveness.savings_error_percent == null
              ? "Pending"
              : `${Number(
                  data.optimizer_effectiveness.savings_error_percent,
                ).toFixed(0)}%`}
          </strong>
          <small>
            {data.optimizer_effectiveness.mission_count} completed missions
          </small>
        </article>
      </div>

      <div className="ml-health-lower-grid">
        <div className="ml-health-governance">
          <div className="ml-health-subheading">
            <div>
              <span>Governance decision</span>
              <h4>
                {data.retrain_recommended
                  ? "Retraining is recommended"
                  : data.health_status === "Watch"
                    ? "Continue monitoring"
                    : "Production model remains healthy"}
              </h4>
            </div>
          </div>

          <ul>
            {data.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>

        <div className="ml-health-drift">
          <div className="ml-health-subheading">
            <div>
              <span>Data drift</span>
              <h4>Largest feature shifts</h4>
            </div>
          </div>

          {topDrift.length ? (
            <div className="ml-health-drift-list">
              {topDrift.map((feature) => (
                <div key={feature.feature}>
                  <span>
                    {feature.feature.replaceAll("_", " ")}
                  </span>
                  <strong>{feature.standardized_shift.toFixed(2)}</strong>
                  <em
                    className={`ml-drift-${feature.status.toLowerCase()}`}
                  >
                    {feature.status}
                  </em>
                </div>
              ))}
            </div>
          ) : (
            <p>No drift sample is available yet.</p>
          )}
        </div>
      </div>

      {!facilityId && data.facility_performance.length > 0 && (
        <div className="ml-health-facilities">
          <div className="ml-health-subheading">
            <div>
              <span>Facility monitoring</span>
              <h4>Accuracy by warehouse</h4>
            </div>
          </div>

          <div className="ml-health-table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>Sample</th>
                  <th>Turn MAE</th>
                  <th>SLA precision</th>
                  <th>SLA recall</th>
                </tr>
              </thead>
              <tbody>
                {data.facility_performance.map((facility) => (
                  <tr key={facility.facility_id}>
                    <td>{facility.facility_name}</td>
                    <td>{facility.sample_size}</td>
                    <td>{minutes(facility.duration_mae)}</td>
                    <td>{percent(facility.sla_precision)}</td>
                    <td>{percent(facility.sla_recall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
