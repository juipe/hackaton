import { Skeleton } from "@/components/ui/skeleton";
import { formatMoneyRounded } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { SpendingOverTime } from "@/types/api";

/** Столбиков ровно пять: карточка узкая, шестой перестаёт читаться. */
const MONTHS_SHOWN = 5;

/** Самый низкий столбик всё равно виден — иначе месяц без расходов исчезает. */
const MIN_BAR_PERCENT = 6;

/** `2026-08` → `авг`. Точку у сокращённого месяца локаль ставит, макет — нет. */
function monthLabel(month: string): string {
  const [year, index] = (month ?? "").split("-").map((part) => Number.parseInt(part, 10));
  if (!Number.isFinite(year) || !Number.isFinite(index)) return month ?? "";
  const date = new Date(Date.UTC(year, index - 1, 1));
  if (Number.isNaN(date.getTime())) return month;
  return date
    .toLocaleDateString("ru-RU", { month: "short", timeZone: "UTC" })
    .replace(/\.$/, "");
}

/**
 * Мини-график расходов по месяцам: пять div-столбиков, без библиотеки графиков.
 * Здесь не нужны ни оси, ни подсказки — только форма тренда, поэтому recharts
 * (и его вес) в карточку не тянем. Данные — те же, что у большого графика.
 */
export function MonthlyMiniChart({
  data,
  isLoading,
  className,
}: {
  data?: SpendingOverTime;
  isLoading?: boolean;
  className?: string;
}) {
  if (isLoading) {
    return (
      <div className={cn("flex h-16 items-end gap-2.5", className)} aria-hidden>
        {[52, 38, 61, 44, 30].map((height, index) => (
          <Skeleton
            key={index}
            className="flex-1 rounded-b-[3px] rounded-t-[6px]"
            style={{ height: `${height}%` }}
          />
        ))}
      </div>
    );
  }

  const points = (data?.items ?? []).slice(-MONTHS_SHOWN);
  if (points.length === 0) return null;

  const max = points.reduce((top, point) => Math.max(top, point.amount_cents), 0);
  // Выделяем самый дорогой месяц: именно он объясняет форму столбика рядом.
  const peak = points.reduce(
    (best, point, index) => (point.amount_cents > points[best].amount_cents ? index : best),
    0,
  );

  const description = points
    .map((point) => `${monthLabel(point.month)} — ${formatMoneyRounded(point.amount_cents)}`)
    .join(", ");

  return (
    <div className={className} role="img" aria-label={`Расходы по месяцам: ${description}`}>
      <div className="flex h-16 items-end gap-2.5" aria-hidden>
        {points.map((point, index) => {
          const share = max > 0 ? (point.amount_cents / max) * 100 : 0;
          return (
            <div
              key={point.month}
              className={cn(
                "flex-1 rounded-b-[3px] rounded-t-[6px]",
                index === peak ? "bg-primary" : "bg-chart-muted",
              )}
              style={{ height: `${Math.max(share, MIN_BAR_PERCENT)}%` }}
            />
          );
        })}
      </div>
      <div className="mt-2.5 flex gap-2.5 text-xs text-dim" aria-hidden>
        {points.map((point, index) => (
          <span
            key={point.month}
            className={cn(
              "flex-1 text-center",
              index === peak && "font-semibold text-accent-foreground",
            )}
          >
            {monthLabel(point.month)}
          </span>
        ))}
      </div>
    </div>
  );
}
