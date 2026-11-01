import type { ArticleStatus } from "@/lib/api/types";

const styles: Record<ArticleStatus, string> = {
  draft: "bg-sunken text-muted",
  published: "bg-success-soft text-success",
  unpublished: "bg-warn-soft text-warn",
};

const dots: Record<ArticleStatus, string> = {
  draft: "bg-faint",
  published: "bg-success",
  unpublished: "bg-warn",
};

const labels: Record<ArticleStatus, string> = {
  draft: "Draft",
  published: "Published",
  unpublished: "Unpublished",
};

export function StatusBadge({ status }: { status: ArticleStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${dots[status]}`} />
      {labels[status]}
    </span>
  );
}
