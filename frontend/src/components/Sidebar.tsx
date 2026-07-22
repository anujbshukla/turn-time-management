export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">TT</div>

        <div>
          <strong>Turn Time</strong>
          <span>Management</span>
        </div>
      </div>

      <nav className="navigation">
        <button className="nav-item active">
          Operations
        </button>

        <button className="nav-item">
          Appointments
        </button>

        <button className="nav-item">
          Docks
        </button>

        <button className="nav-item">
          Carriers
        </button>

        <button className="nav-item">
          Decision Center
        </button>
      </nav>

      <div className="sidebar-footer">
        <span>Warehouse</span>
        <strong>Atlanta DC</strong>
      </div>
    </aside>
  );
}