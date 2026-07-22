export function Header() {
  return (
    <header className="top-header">
      <div>
        <p className="eyebrow">
          Warehouse Operations Control Tower
        </p>

        <h1>Turn Time Management</h1>

        <p className="header-description">
          Monitor appointments, SLA risk and dock
          performance.
        </p>
      </div>

      <div className="live-status">
        <span className="live-dot" />
        Live Operations
      </div>
    </header>
  );
}