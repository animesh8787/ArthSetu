import { useState } from "react";
import { Check, Copy } from "@/components/icons";
import { cn } from "@/lib/cn";

export function CopyButton({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard blocked — ignore */
        }
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded px-1 text-ink-subtle transition-colors hover:text-ink",
      )}
      aria-label={`Copy ${label ?? value}`}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-ok" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}
