export interface DockUtilizationItem {
  id: string;
  name: string;
  facilityName?: string;
  utilization: number;
  status: string;
}

interface DockUtilizationProps {
  docks: DockUtilizationItem[];
  showFacilityNames?: boolean;
  embedded?: boolean;
}

export function DockUtilization({
  docks,
  showFacilityNames = false,
  embedded = false,
}: DockUtilizationProps) {
  const content = (
    <>
      {!embedded && (
        <div className="panel-header">
          <div>
            <h2>Dock Utilization</h2>
            <p>
              Current utilization and attention status
              {showFacilityNames ? " across all facilities" : ""}
            </p>
          </div>
        </div>
      )}

      <div className="dock-grid">
        {docks.map((dock) => (
          <article className="dock-card" key={dock.id}>
            <div className="dock-card-heading">
              <div>
                <strong>{dock.name}</strong>
                {showFacilityNames && dock.facilityName && (
                  <span className="dock-facility-name">
                    {dock.facilityName}
                  </span>
                )}
              </div>
              <span>{Math.round(dock.utilization)}%</span>
            </div>

            <div className="utilization-track">
              <div
                className="utilization-fill"
                style={{ width: `${Math.max(0, Math.min(100, dock.utilization))}%` }}
              />
            </div>

            <p>{dock.status}</p>
          </article>
        ))}

        {docks.length === 0 && (
          <div className="dock-empty-state">
            No docks are available for the selected operating window.
          </div>
        )}
      </div>
    </>
  );

  if (embedded) {
    return <div className="dock-utilization-embedded">{content}</div>;
  }

  return <section className="panel dock-panel">{content}</section>;
}
