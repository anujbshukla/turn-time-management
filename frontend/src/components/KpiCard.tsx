interface KpiCardProps {
  label: string;
  value: string;
  detail: string;
}

export function KpiCard({
  label,
  value,
  detail,
}: KpiCardProps) {
  return (
    <article className="kpi-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}