import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Recharts hands the tooltip whatever datum produced the hovered shape. Typing the
 * payload here keeps each chart's tooltip honest about the row it is reading.
 */
export interface ChartTooltipEntry<TPayload> {
  name?: string;
  value?: number | string;
  dataKey?: string | number;
  color?: string;
  payload?: TPayload;
}

export interface ChartTooltipProps<TPayload> {
  active?: boolean;
  label?: string | number;
  payload?: ChartTooltipEntry<TPayload>[];
}

/**
 * The tooltip is a small card in the same language as every other surface:
 * no border, soft shadow, `rounded-tile`. It floats over the chart, so the
 * shadow — not an outline — is what lifts it off the plot area.
 */
export function ChartTooltipCard({
  title,
  children,
  className,
}: {
  title: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "min-w-[11rem] rounded-tile bg-card px-4 py-3 shadow-card",
        className,
      )}
    >
      <p className="text-[13px] font-medium text-dim">{title}</p>
      <div className="mt-2 space-y-1.5">{children}</div>
    </div>
  );
}

export function ChartTooltipRow({
  color,
  label,
  value,
  valueClassName,
}: {
  color?: string;
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-6 text-[15px]">
      <span className="flex min-w-0 items-center gap-2.5 text-foreground">
        {color ? (
          <span
            className="size-2.5 shrink-0 rounded-[3px]"
            style={{ backgroundColor: color }}
            aria-hidden
          />
        ) : null}
        <span className="truncate">{label}</span>
      </span>
      <span className={cn("tabular-nums-money font-semibold text-foreground", valueClassName)}>
        {value}
      </span>
    </div>
  );
}
