import { useMemo, useState } from "react";
import type { CSSProperties } from "react";

import type {
  WarehouseHeatmapData,
  WarehouseHeatmapDock,
  WarehouseHeatmapLayer,
} from "../types/dashboard";

type Props = {
  data: WarehouseHeatmapData;
  onOpenAppointment: (appointmentId: string) => void;
  onRunWhatIf: () => void;
  onFilterDock: (dockId?: string) => void;
  embedded?: boolean;
  limitToTopTen?: boolean;
};

const LAYERS: Array<{ key: WarehouseHeatmapLayer; label: string }> = [
  { key: "risk", label: "Overall risk" },
  { key: "utilization", label: "Utilization" },
  { key: "queue", label: "Queue" },
  { key: "sla", label: "SLA risk" },
  { key: "detention", label: "Detention" },
  { key: "recovery", label: "Recovery value" },
];

export function WarehouseRiskHeatMap({
  data,
  onOpenAppointment,
  onRunWhatIf,
  onFilterDock,
  embedded = false,
  limitToTopTen = false,
}: Props) {
  const [layer, setLayer] = useState<WarehouseHeatmapLayer>("risk");
  const [selectedDockId, setSelectedDockId] = useState<string | null>(null);

  const docks = useMemo(
    () => limitToTopTen
      ? [...data.docks]
        .sort((left, right) =>
          right.risk_score - left.risk_score ||
          right.utilization_percent - left.utilization_percent
        )
        .slice(0, 10)
      : data.docks,
    [data.docks, limitToTopTen],
  );
  const multipleFacilities = limitToTopTen || data.facilities.length > 1;
  const selectedDock = docks.find((dock) => dock.dock_id === selectedDockId) ?? null;
  const maxValue = Math.max(1, ...docks.map((dock) => layerValue(dock, layer)));

  const scopeSummary = useMemo(() => {
    if (!limitToTopTen && data.facilities.length === 1) {
      const facility = data.facilities[0];
      return {
        label: facility.facility_name,
        health: facility.health,
        averageUtilization: facility.average_utilization,
        criticalDocks: facility.critical_docks,
        detentionExposure: facility.detention_exposure,
      };
    }

    const riskScore = data.facilities.reduce(
      (highest, facility) => Math.max(highest, facility.risk_score),
      0,
    );
    const averageUtilization = docks.length
      ? docks.reduce((total, dock) => total + dock.utilization_percent, 0) / docks.length
      : 0;

    return {
      label: "All facilities",
      health: healthFromRisk(riskScore),
      averageUtilization,
      criticalDocks: data.facilities.reduce(
        (total, facility) => total + facility.critical_docks,
        0,
      ),
      detentionExposure: data.facilities.reduce(
        (total, facility) => total + facility.detention_exposure,
        0,
      ),
    };
  }, [data.facilities, docks, limitToTopTen]);

  const body = (
    <>
      {!embedded && (
        <div className="warehouse-heatmap-header">
          <div>
            <span className="panel-eyebrow">Spatial operations intelligence</span>
            <h2>Warehouse Risk Heat Map</h2>
            <p>See dock pressure, congestion, SLA exposure and recovery opportunity in one view.</p>
          </div>
        </div>
      )}

      <div className="warehouse-heatmap-scope-bar">
        <span>Facility scope</span>
        <strong>{scopeSummary.label}</strong>
      </div>

      <div className="warehouse-heatmap-facility-summary">
        <div>
          <span>{multipleFacilities ? "Overall health" : "Facility health"}</span>
          <strong className={`heatmap-health-text ${scopeSummary.health.toLowerCase()}`}>
            {scopeSummary.health}
          </strong>
        </div>
        <div><span>Average utilization</span><strong>{Math.round(scopeSummary.averageUtilization)}%</strong></div>
        <div><span>Critical docks</span><strong>{scopeSummary.criticalDocks}</strong></div>
        <div><span>Detention exposure</span><strong>{formatCurrency(scopeSummary.detentionExposure)}</strong></div>
      </div>

      <div className="warehouse-heatmap-layers" role="group" aria-label="Heat map layer">
        {LAYERS.map((option) => (
          <button
            key={option.key}
            type="button"
            className={layer === option.key ? "active" : ""}
            onClick={() => setLayer(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="warehouse-floor-shell">
        <div className="warehouse-floor-label receiving">Receiving</div>
        <div className="warehouse-floor-label shipping">Shipping</div>

        <div className="warehouse-dock-grid">
          {docks.map((dock) => {
            const value = layerValue(dock, layer);
            const intensity = Math.max(0.08, value / maxValue);
            const selected = selectedDockId === dock.dock_id;

            return (
              <button
                key={`${dock.facility_id}-${dock.dock_id}`}
                type="button"
                className={`warehouse-dock-tile ${dock.health.toLowerCase()} ${selected ? "selected" : ""}`}
                style={{ "--heat-intensity": intensity } as CSSProperties}
                onClick={() => setSelectedDockId(selected ? null : dock.dock_id)}
                aria-pressed={selected}
              >
                <div className="warehouse-dock-tile-heading">
                  <div>
                    <strong>{dock.dock_name}</strong>
                    {multipleFacilities && (
                      <small>{dock.facility_name}</small>
                    )}
                  </div>
                  <span>{dock.zone}</span>
                </div>
                <div className="warehouse-dock-primary-value">
                  <strong>{formatLayerValue(value, layer)}</strong>
                  <span>{layerLabel(layer)}</span>
                </div>
                <div className="warehouse-dock-mini-metrics">
                  <span>{dock.active_appointments} active</span>
                  <span>{dock.queue_length} queued</span>
                  <span>{dock.sla_risk_count} SLA risk</span>
                </div>
                {dock.predicted_congestion && <i>Congestion predicted</i>}
              </button>
            );
          })}
        </div>

        {docks.length === 0 && (
          <div className="warehouse-heatmap-empty">No active docks are available for the selected facility scope.</div>
        )}
      </div>

      <div className="warehouse-heatmap-legend">
        {data.legend.map((item) => (
          <span key={item.health} className={item.health.toLowerCase()}>
            <i /> {item.health}
          </span>
        ))}
      </div>

      {selectedDock && (
        <div className="warehouse-dock-detail-panel">
          <div>
            <span className="panel-eyebrow">Selected dock intelligence</span>
            <h3>{selectedDock.dock_name} · {selectedDock.facility_name}</h3>
            <p>{selectedDock.recommended_action}</p>
          </div>

          <div className="warehouse-dock-detail-metrics">
            <div><span>Risk score</span><strong>{Math.round(selectedDock.risk_score)}</strong></div>
            <div><span>Utilization</span><strong>{Math.round(selectedDock.utilization_percent)}%</strong></div>
            <div><span>Avg. delay</span><strong>{Math.round(selectedDock.average_delay_minutes)} min</strong></div>
            <div><span>Exposure</span><strong>{formatCurrency(selectedDock.detention_exposure)}</strong></div>
            <div><span>Recovery value</span><strong>{formatCurrency(selectedDock.recovery_opportunity)}</strong></div>
          </div>

          <div className="warehouse-dock-detail-actions">
            {selectedDock.highest_risk_appointment_id && (
              <button type="button" className="primary-button" onClick={() => onOpenAppointment(selectedDock.highest_risk_appointment_id!)}>
                Open highest-risk appointment
              </button>
            )}
            <button
              type="button"
              className="secondary-button"
              onClick={() => onFilterDock(selectedDock.dock_id)}
            >
              View impacted queue
            </button>
            <button type="button" className="secondary-button" onClick={onRunWhatIf}>
              Run What-If
            </button>
          </div>
        </div>
      )}
    </>
  );

  if (embedded) {
    return <div className="warehouse-risk-heatmap-embedded">{body}</div>;
  }

  return <section className="panel warehouse-risk-heatmap-panel">{body}</section>;
}

function layerValue(dock: WarehouseHeatmapDock, layer: WarehouseHeatmapLayer) {
  if (layer === "utilization") return dock.utilization_percent;
  if (layer === "queue") return dock.queue_length;
  if (layer === "sla") return dock.sla_risk_count;
  if (layer === "detention") return dock.detention_exposure;
  if (layer === "recovery") return dock.recovery_opportunity;
  return dock.risk_score;
}

function layerLabel(layer: WarehouseHeatmapLayer) {
  if (layer === "utilization") return "utilization";
  if (layer === "queue") return "appointments queued";
  if (layer === "sla") return "appointments at risk";
  if (layer === "detention") return "detention exposure";
  if (layer === "recovery") return "recovery opportunity";
  return "risk score";
}

function formatLayerValue(value: number, layer: WarehouseHeatmapLayer) {
  if (layer === "utilization") return `${Math.round(value)}%`;
  if (layer === "detention" || layer === "recovery") return formatCurrency(value);
  return Math.round(value).toLocaleString();
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function healthFromRisk(score: number) {
  if (score >= 75) return "Critical";
  if (score >= 55) return "High";
  if (score >= 30) return "Watch";
  return "Healthy";
}
