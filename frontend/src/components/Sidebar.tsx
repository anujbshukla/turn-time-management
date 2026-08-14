import type { AppointmentReferenceItem } from "../types/appointments";

interface SidebarProps {
  facilityId?: string;
  facilities: AppointmentReferenceItem[];
  onFacilityChange: (facilityId?: string) => void;
}

export function Sidebar({
  facilityId,
  facilities,
  onFacilityChange,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">CT</div>

        <div>
          <strong>Warehouse Operations</strong>
          <span>Control Tower</span>
        </div>
      </div>

      <nav className="navigation">
        <button className="nav-item active">Operations</button>
        <button className="nav-item">Appointments</button>
        <button className="nav-item">Docks</button>
        <button className="nav-item">Carriers</button>
        <button className="nav-item">Decision Center</button>
      </nav>

      <div className="sidebar-footer facility-sidebar-filter">
        <label htmlFor="sidebar-facility">Facility</label>
        <select
          id="sidebar-facility"
          value={facilityId ?? ""}
          onChange={(event) =>
            onFacilityChange(event.target.value || undefined)
          }
        >
          <option value="">All facilities</option>
          {facilities.map((facility) => (
            <option key={facility.id} value={facility.id}>
              {facility.label}
            </option>
          ))}
        </select>
      </div>
    </aside>
  );
}
