import { AppointmentTable } from "../components/AppointmentTable";
import { BestNextAction } from "../components/BestNextAction";
import { DockUtilization } from "../components/DockUtilization";
import { Header } from "../components/Header";
import { KpiCard } from "../components/KpiCard";

import {
  currentRecommendation,
  dashboardKpis,
  docks,
} from "../data/dockData";

import { useAppointments } from "../hooks/useAppointments";

export function OperationsPage() {
  const {
    appointments,
    loading,
    error,
  } = useAppointments();

  return (
    <>
      <Header />

      <section className="kpi-grid">
        {dashboardKpis.map((kpi) => (
          <KpiCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            detail={kpi.detail}
          />
        ))}
      </section>

      <section className="content-grid">
        <AppointmentTable
          appointments={appointments}
          loading={loading}
          error={error}
        />

        <BestNextAction
          recommendation={currentRecommendation}
        />
      </section>

      <DockUtilization docks={docks} />
    </>
  );
}