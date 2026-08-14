import { useEffect, useState } from "react";

import "./App.css";

import { DashboardLayout } from "./layouts/DashboardLayout";
import { OperationsPage } from "./pages/OperationsPage";
import { useAppointmentReferenceData } from "./hooks/useAppointmentReferenceData";
import type { AppointmentReferenceItem } from "./types/appointments";

const DEFAULT_FACILITY_ID = "FAC001";

function App() {
  const [facilityId, setFacilityId] =
    useState<string | undefined>(DEFAULT_FACILITY_ID);
  const [availableFacilities, setAvailableFacilities] =
    useState<AppointmentReferenceItem[] | null>(null);
  const { referenceData } = useAppointmentReferenceData();

  const facilityOptions = availableFacilities ?? referenceData.facilities;

  useEffect(() => {
    if (
      availableFacilities &&
      facilityId &&
      !availableFacilities.some((facility) => facility.id === facilityId)
    ) {
      setFacilityId(undefined);
    }
  }, [availableFacilities, facilityId]);

  return (
    <DashboardLayout
      facilityId={facilityId}
      facilities={facilityOptions}
      onFacilityChange={setFacilityId}
    >
      <OperationsPage
        facilityId={facilityId}
        referenceData={referenceData}
        onAvailableFacilitiesChange={setAvailableFacilities}
      />
    </DashboardLayout>
  );
}

export default App;
