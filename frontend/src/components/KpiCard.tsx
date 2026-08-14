interface KpiCardProps {
  label: string;
  value: string;
  detail: string;
  index?: number;
}

export function KpiCard({
  label,
  value,
  detail,
  index = 0,
}: KpiCardProps) {
  return (
    <article className="kpi-card">
      <div className="kpi-card-topline">
        <span>{label}</span>
        <span className="kpi-card-index" aria-hidden="true">
          {String(index + 1).padStart(2, "0")}
        </span>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
      <div className="kpi-card-accent" aria-hidden="true" />
    </article>
  );
}
