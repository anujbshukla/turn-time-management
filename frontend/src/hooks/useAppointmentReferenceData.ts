import { useEffect, useState } from "react";

import { getAppointmentReferenceData } from "../services/appointments";
import type { AppointmentReferenceData } from "../types/appointments";

const EMPTY_REFERENCE_DATA: AppointmentReferenceData = {
  facilities: [],
  customers: [],
  carriers: [],
  docks: [],
  products: [],
};

export function useAppointmentReferenceData() {
  const [referenceData, setReferenceData] =
    useState<AppointmentReferenceData>(EMPTY_REFERENCE_DATA);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await getAppointmentReferenceData();
        if (!cancelled) setReferenceData(response);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { referenceData, loading };
}
