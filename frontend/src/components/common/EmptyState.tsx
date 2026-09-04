import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

/**
 * Пустое состояние живёт внутри карточки, поэтому оно само — не карточка, а
 * мягкий блок на заливке `--subtle`. Пунктирная рамка ушла вместе со старым
 * языком: форму держит скругление и заливка, а не обводка.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-row bg-subtle px-5 py-9 text-center sm:px-6 sm:py-10",
        className,
      )}
    >
      {Icon ? (
        <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground">
          <Icon className="size-6" aria-hidden />
        </span>
      ) : null}
      <div className="space-y-1.5">
        <p className="text-[19px] font-bold leading-tight tracking-[-0.02em] text-foreground">
          {title}
        </p>
        {description ? (
          <p className="mx-auto max-w-[44ch] text-[15px] leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="pt-0.5">{action}</div> : null}
    </div>
  );
}
