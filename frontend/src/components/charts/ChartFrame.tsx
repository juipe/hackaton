import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface ChartFrameProps {
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyLabel: string;
  emptyIcon?: LucideIcon;
  className?: string;
  children: ReactNode;
}

/**
 * Axes, grid lines and the hover cursor get their colours from Recharts itself —
 * there is no prop to hand them a design token. Targeting the class names Recharts
 * always emits is the one reliable way to keep that furniture on the palette
 * instead of on hardcoded hexes. (Series colours are different: those we pass in,
 * so a chart can use `hsl(var(--positive))` directly.)
 */
const CHART_SURFACE = [
  "[&_.recharts-cartesian-axis-tick-value]:fill-dim",
  "[&_.recharts-cartesian-axis-tick-value]:text-[12px]",
  "[&_.recharts-cartesian-grid_line]:stroke-border",
  "[&_.recharts-reference-line-line]:stroke-border",
  "[&_.recharts-tooltip-cursor]:fill-subtle",
  "[&_.recharts-surface]:outline-none",
].join(" ");

/**
 * The fixed-height chart area. Loading and empty renders occupy exactly the same
 * box as the chart itself, so the dashboard never reflows as queries resolve.
 */
export function ChartFrame({
  isLoading,
  isEmpty,
  emptyLabel,
  emptyIcon: Icon,
  className,
  children,
}: ChartFrameProps) {
  return (
    <div className={cn("h-[240px] w-full lg:h-[280px]", CHART_SURFACE, className)}>
      {isLoading ? (
        <Skeleton className="h-full w-full rounded-tile" />
      ) : isEmpty ? (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2.5 rounded-tile bg-subtle px-6 text-center">
          {Icon ? <Icon className="size-[22px] text-faint" aria-hidden /> : null}
          <p className="text-[15px] text-dim">{emptyLabel}</p>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
