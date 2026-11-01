import { Button } from "@/components/ui/button";

export function ConflictView({
  currentDraftVersion,
  busy,
  onReload,
  onResubmit,
}: {
  currentDraftVersion: number | undefined;
  busy: boolean;
  onReload: () => void;
  onResubmit: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-warn bg-warn-soft p-4 text-sm">
      <p className="font-semibold text-warn">The server copy changed</p>
      <p className="mt-1 text-ink">
        Someone saved this article after you opened it. Your unsent changes are still in the form
        below, and nothing was overwritten.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={onReload} disabled={busy}>
          Reload the latest (discard my changes)
        </Button>
        <Button variant="primary" onClick={onResubmit} disabled={busy || currentDraftVersion === undefined}>
          Resubmit mine against the new version
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted">
        Resubmitting replaces the newer draft with yours.
      </p>
    </div>
  );
}
