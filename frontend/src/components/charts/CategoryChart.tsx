import { PieChart as PieChartIcon } from "lucide-react";
import { Cell, Pie, PieChart, Tooltip } from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import {
  ChartTooltipCard,
  ChartTooltipRow,
  type ChartTooltipProps,
} from "@/components/charts/ChartTooltipCard";
import { Skeleton } from "@/components/ui/skeleton";
import { CHART_COLORS } from "@/lib/constants";
import { plural } from "@/lib/format";
import { formatMoney, formatMoneyRounded } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { CategoryBreakdown, CategoryBreakdownItem } from "@/types/api";

interface CategorySlice extends CategoryBreakdownItem {
  color: string;
}

/**
 * Донат из макета: внешний круг 176px, дырка 122px. Радиусы заданы в пикселях,
 * а не в процентах, — иначе кольцо «дышит» вместе с шириной карточки и перестаёт
 * совпадать с числом в центре.
 */
const DONUT_SIZE = 176;
const DONUT_OUTER_RADIUS = 88;
const DONUT_INNER_RADIUS = 61;

/** Сколько категорий показываем строками; остальные сворачиваются в капсулу. */
const LEGEND_ROWS = 5;

/** `12.34` → `12,3%`: one decimal, Russian comma, no space before the sign. */
function formatPercentage(value: number): string {
  const safe = Number.isFinite(value) ? value : 0;
  return `${safe.toFixed(1).replace(".", ",")}%`;
}

function CategoryTooltip({
  active,
  payload,
  currency,
}: ChartTooltipProps<CategorySlice> & { currency: string }) {
  const slice = active ? payload?.[0]?.payload : undefined;
  if (!slice) return null;
  return (
    <ChartTooltipCard title="Расходы по категориям">
      <ChartTooltipRow
        color={slice.color}
        label={slice.name}
        value={formatMoney(slice.amount_cents, currency)}
      />
      <p className="text-[13px] text-dim">
        {formatPercentage(slice.percentage)} от общей суммы ·{" "}
        {plural(slice.expense_count, "расход", "расхода", "расходов")}
      </p>
    </ChartTooltipCard>
  );
}

/** Кружок-заглушка ровно того же размера, что и донат: карточка не прыгает. */
function CategoryChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-7",
        className,
      )}
      aria-hidden
    >
      <Skeleton className="size-[176px] shrink-0 rounded-full" />
      <ul className="flex w-full min-w-0 flex-1 flex-col gap-3">
        {[0, 1, 2, 3, 4].map((row) => (
          <li key={row} className="flex items-center gap-2.5">
            <Skeleton className="size-2.5 shrink-0 rounded-[3px]" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-20 shrink-0" />
            <Skeleton className="h-4 w-11 shrink-0" />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CategoryChart({
  data,
  currency,
  isLoading,
  className,
}: {
  data?: CategoryBreakdown;
  currency: string;
  isLoading?: boolean;
  className?: string;
}) {
  const slices: CategorySlice[] = (data?.items ?? []).map((item, index) => ({
    ...item,
    color: CHART_COLORS[index % CHART_COLORS.length],
  }));
  const total = data?.total_cents ?? 0;
  const isEmpty = slices.length === 0;

  if (isLoading) {
    return <CategoryChartSkeleton className={className} />;
  }

  if (isEmpty) {
    return (
      <ChartFrame
        isEmpty
        emptyIcon={PieChartIcon}
        emptyLabel="За этот период расходов пока нет."
        className={cn("h-[176px] lg:h-[176px]", className)}
      >
        {null}
      </ChartFrame>
    );
  }

  const visible = slices.slice(0, LEGEND_ROWS);
  const hidden = slices.length - visible.length;

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-7",
        className,
      )}
    >
      <div
        className="relative shrink-0"
        style={{ width: DONUT_SIZE, height: DONUT_SIZE }}
      >
        <PieChart width={DONUT_SIZE} height={DONUT_SIZE}>
          <Pie
            data={slices}
            dataKey="amount_cents"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={DONUT_INNER_RADIUS}
            outerRadius={DONUT_OUTER_RADIUS}
            paddingAngle={1.5}
            stroke="none"
            isAnimationActive={false}
          >
            {slices.map((slice) => (
              <Cell key={slice.category_id} fill={slice.color} />
            ))}
          </Pie>
          <Tooltip content={<CategoryTooltip currency={currency} />} />
        </PieChart>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="text-xs text-dim">Всего</span>
          <span className="tabular-nums-money text-[17px] font-bold tracking-[-0.02em]">
            {formatMoneyRounded(total)}
          </span>
        </div>
      </div>

      {/*
       * Название переносится, а не обрезается. В макете строка одна, но там
       * легенда шире: русские категории длиннее английских («Кафе и рестораны»
       * против «Food»), и в двухколоночной сетке дашборда самая длинная не
       * влезает. Обрезанное название читается хуже, чем строка в два ряда,
       * поэтому числа выравниваются по первой строке, а имя занимает столько,
       * сколько нужно.
       */}
      <ul className="flex w-full min-w-0 flex-1 flex-col gap-3">
        {visible.map((slice) => (
          <li key={slice.category_id} className="flex items-start gap-2.5">
            <span
              className="mt-[6px] size-2.5 shrink-0 rounded-[3px]"
              style={{ backgroundColor: slice.color }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 text-[15px] leading-[1.35]">{slice.name}</span>
            <span className="tabular-nums-money shrink-0 text-[15px] font-semibold leading-[1.35]">
              {formatMoneyRounded(slice.amount_cents)}
            </span>
            <span className="tabular-nums-money w-11 shrink-0 text-right text-[13px] leading-[1.35] text-dim">
              {formatPercentage(slice.percentage)}
            </span>
          </li>
        ))}
        {hidden > 0 ? (
          <li className="mt-1">
            <span className="inline-flex items-center rounded-full bg-secondary px-3.5 py-[7px] text-[13px] font-semibold text-muted-foreground">
              и ещё {plural(hidden, "категория", "категории", "категорий")}
            </span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
