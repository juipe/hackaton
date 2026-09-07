import { AlertTriangle, Gauge } from "lucide-react";
import { Link } from "react-router-dom";

import { SectionCard } from "@/components/common/SectionCard";
import { useBudgetStatus } from "@/hooks/useDashboard";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";

/**
 * «Критическая точка бюджета» на главной: полоса заполнения лимита за текущий
 * месяц. Не рендерится, пока лимит не задан в профиле — карточка не должна
 * упрашивать пользователя её настроить с порога.
 */
export function BudgetStatusCard() {
  const { data } = useBudgetStatus();

  if (!data || data.level === "none" || data.monthly_budget_cents === null) {
    return null;
  }

  const ratio = Math.min(data.usage_percent, 100);
  const over = data.remaining_cents !== null && data.remaining_cents < 0;
  const barTone =
    data.level === "critical"
      ? "bg-negative"
      : data.level === "warning"
        ? "bg-warning"
        : "bg-primary";

  return (
    <SectionCard
      title="Критическая точка бюджета"
      description={`Потрачено в этом месяце: ${formatMoney(data.spent_cents, data.currency)} из ${formatMoney(data.monthly_budget_cents, data.currency)}`}
      action={
        data.level === "ok" ? (
          <Gauge className="size-5 text-dim" aria-hidden />
        ) : (
          <AlertTriangle
            className={cn(
              "size-5",
              data.level === "critical" ? "text-negative" : "text-warning-strong",
            )}
            aria-hidden
          />
        )
      }
    >
      <div className="flex flex-col gap-3">
        <div
          className="h-2.5 overflow-hidden rounded-full bg-subtle"
          role="progressbar"
          aria-valuenow={Math.round(data.usage_percent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Использование месячного бюджета"
        >
          <div
            className={cn("h-full rounded-full transition-all", barTone)}
            style={{ width: `${ratio}%` }}
          />
        </div>

        {data.level === "critical" ? (
          <p className="text-[13px] font-medium text-negative">
            {over && data.remaining_cents !== null
              ? `Критическая точка превышена на ${formatMoney(-data.remaining_cents, data.currency)}.`
              : "Вы достигли критической точки бюджета."}
          </p>
        ) : data.level === "warning" ? (
          <p className="text-[13px] font-medium text-warning-strong">
            Вы приблизились к критической точке — осталось{" "}
            {formatMoney(data.remaining_cents ?? 0, data.currency)}.
          </p>
        ) : (
          <p className="text-[13px] text-dim">
            Осталось {formatMoney(data.remaining_cents ?? 0, data.currency)} свободных
            денег в этом месяце.
          </p>
        )}

        <p className="text-[12px] text-faint">
          Лимит настраивается в{" "}
          <Link to="/profile" className="underline underline-offset-2 hover:text-dim">
            профиле
          </Link>
          . Считается ваша личная доля в расходах всех групп.
        </p>
      </div>
    </SectionCard>
  );
}
