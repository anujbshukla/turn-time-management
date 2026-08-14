import type { ReactNode } from "react";

import { Sidebar } from "../components/Sidebar";
import type { AppointmentReferenceItem } from "../types/appointments";

interface DashboardLayoutProps {
  children: ReactNode;
  facilityId?: string;
  facilities: AppointmentReferenceItem[];
  onFacilityChange: (facilityId?: string) => void;
}

export function DashboardLayout({
  children,
  facilityId,
  facilities,
  onFacilityChange,
}: DashboardLayoutProps) {
  return (
    <div className="app-layout">
      <Sidebar
        facilityId={facilityId}
        facilities={facilities}
        onFacilityChange={onFacilityChange}
      />

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
