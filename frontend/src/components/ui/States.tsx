import type { ReactNode } from "react";
import { Refresh } from "@/components/icons";
import { Button } from "./Button";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && (
        <p className="max-w-sm text-[13px] text-ink-muted">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      title="Something went wrong"
      description={message ?? "The request could not be completed."}
      action={
        onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <Refresh className="h-3.5 w-3.5" />
            Try again
          </Button>
        )
      }
    />
  );
}
