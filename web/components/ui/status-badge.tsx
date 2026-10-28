export type BadgeTone = "neutral" | "success" | "warning" | "danger";

export function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
}) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}
