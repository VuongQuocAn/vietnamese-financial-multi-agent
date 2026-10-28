import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={26} strokeWidth={1.5} />
      </span>
      <p className="empty-title">{title}</p>
      {description && <p className="muted">{description}</p>}
    </div>
  );
}
