import { BarChart3 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import {
  ChartTooltipCard,
  ChartTooltipRow,
  type ChartTooltipProps,
} from "@/components/charts/ChartTooltipCard";
import { formatCompact, formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { SpendingOverTime } from "@/types/api";

/**
 * Столбики берут не палитру категорий, а токены интерфейса: сумма группы —
 * фирменный зелёный, ваша доля — его приглушённый оттенок `--chart-muted`.
 * Две величины одного рода читаются как один ряд, а не как две категории.
 */
const TOTAL_COLOR = "hsl(var(--primary))";
const SHARE_COLOR = "hsl(var(--chart-muted))";

const TOTAL_LABEL = "Всего в группе";
const SHARE_LABEL = "Ваша доля";

/**
 * The API ships an English `label` (`Aug 2026`) next to the machine-readable
 * `month` key. The axis and the tooltip are built from the key instead, so the
 * month names always come out of the `ru-RU` locale.
 */
const MONTH_TICK_FORMAT = new Intl.DateTimeFormat("ru-RU", {
  month: "short",
  timeZone: "UTC",
});
const MONTH_TITLE_FORMAT = new Intl.DateTimeFormat("ru-RU", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

interface MonthPoint {
  month: string;
  label: string;
  short: string;
  total: number;
  mine: number;
}

/** `2026-08` → the first of that month in UTC, or `null` for anything unparseable. */
function monthDate(key: string): Date | null {
  const match = /^(\d{4})-(\d{2})$/.exec(key ?? "");
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  return new Date(Date.UTC(year, month - 1, 1));
}

/** `2026-08` → `Август 2026`; the locale's trailing ` г.` is dropped. */
function monthTitle(key: string, fallback: string): string {
  const date = monthDate(key);
  if (!date) return fallback;
  const text = MONTH_TITLE_FORMAT.format(date).replace(/\s*г\.?$/u, "").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** `2026-08` → `авг`, or `авг 26` once the range crosses a year boundary. */
function monthTick(key: string, fallback: string, multiYear: boolean): string {
  const date = monthDate(key);
  if (!date) return fallback;
  const month = MONTH_TICK_FORMAT.format(date).replace(/\.$/, "");
  return multiYear ? `${month} ${String(date.getUTCFullYear()).slice(2)}` : month;
}

function MonthTooltip({
  active,
  payload,
  currency,
}: ChartTooltipProps<MonthPoint> & { currency: string }) {
  const point = active ? payload?.[0]?.payload : undefined;
  if (!point) return null;
  return (
    <ChartTooltipCard title={point.label}>
      <ChartTooltipRow
        color={TOTAL_COLOR}
        label={TOTAL_LABEL}
        value={formatMoney(point.total, currency)}
      />
      <ChartTooltipRow
        color={SHARE_COLOR}
        label={SHARE_LABEL}
        value={formatMoney(point.mine, currency)}
      />
    </ChartTooltipCard>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-2">
      <span
        className="size-2.5 rounded-[3px]"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      {label}
    </span>
  );
}

export function MonthlySpendChart({
  data,
  currency,
  isLoading,
  className,
}: {
  data?: SpendingOverTime;
  currency: string;
  isLoading?: boolean;
  className?: string;
}) {
  const items = data?.items ?? [];
  const multiYear = new Set(items.map((item) => item.month.slice(0, 4))).size > 1;
  const points: MonthPoint[] = items.map((item) => ({
    month: item.month,
    label: monthTitle(item.month, item.label),
    short: monthTick(item.month, item.label, multiYear),
    total: item.amount_cents,
    mine: item.your_share_cents,
  }));
  const isEmpty = points.length === 0;

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[13px] text-dim">
        <LegendSwatch color={TOTAL_COLOR} label={TOTAL_LABEL} />
        <LegendSwatch color={SHARE_COLOR} label={SHARE_LABEL} />
      </div>
      <ChartFrame
        isLoading={isLoading}
        isEmpty={isEmpty}
        emptyIcon={BarChart3}
        emptyLabel="За этот период расходов по месяцам пока нет."
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barGap={3}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="short"
              tickLine={false}
              axisLine={false}
              tickMargin={10}
              minTickGap={8}
              interval="preserveStartEnd"
            />
            {/* `1,2 тыс ₽` is a good deal wider than `1.2k` — the axis needs the room. */}
            <YAxis
              width={72}
              tickLine={false}
              axisLine={false}
              tickMargin={6}
              tickFormatter={(value: number) => formatCompact(Number(value), currency)}
            />
            <Tooltip
              content={<MonthTooltip currency={currency} />}
              cursor={{ fillOpacity: 1 }}
            />
            <Bar dataKey="total" fill={TOTAL_COLOR} radius={[6, 6, 0, 0]} maxBarSize={28} />
            <Bar dataKey="mine" fill={SHARE_COLOR} radius={[6, 6, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  );
}
