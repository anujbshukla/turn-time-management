import type {
  DockStatus,
} from "../types/dashboard";

interface DockUtilizationProps {
  docks: DockStatus[];
}

export function DockUtilization({
  docks,
}: DockUtilizationProps) {
  return (
    <section className="panel dock-panel">
      <div className="panel-header">
        <div>
          <h2>Dock Utilization</h2>
          <p>
            Current utilization and attention status
          </p>
        </div>
      </div>

      <div className="dock-grid">
        {docks.map((dock) => (
          <article
            className="dock-card"
            key={dock.name}
          >
            <div className="dock-card-heading">
              <strong>{dock.name}</strong>
              <span>{dock.utilization}%</span>
            </div>

            <div className="utilization-track">
              <div
                className="utilization-fill"
                style={{
                  width: `${dock.utilization}%`,
                }}
              />
            </div>

            <p>{dock.status}</p>
          </article>
        ))}
      </div>
    </section>
  );
}