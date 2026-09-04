import { ArrowLeftRight, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { BalanceCard } from "@/components/balances/BalanceCard";
import { MonthlyMiniChart } from "@/components/dashboard/MonthlyMiniChart";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { plural } from "@/lib/format";
import { balanceToneClass, formatMoney, formatSigned } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { DashboardGroupSummary, DashboardSummary, SpendingOverTime } from "@/types/api";

interface SummaryCardsProps {
  summary?: DashboardSummary;
  isLoading?: boolean;
  /** Trails the spending hint, e.g. «27 расходов · этот месяц». */
  periodLabel?: string;
  /** Тот же ответ, что кормит график по месяцам, — новых запросов не заводим. */
  monthly?: SpendingOverTime;
  isMonthlyLoading?: boolean;
  /** График по месяцам не пришёл: вместо него — честная строка, а не пустота. */
  isMonthlyError?: boolean;
}

/** Пояснение под герой-числом: чей это плюс и по скольким группам он собран. */
function netCaption(netCents: number, groupCount: number): string {
  const groups = plural(groupCount, "группе", "группам", "группам");
  if (netCents > 0) return `В целом вам должны — по ${groups} сразу.`;
  if (netCents < 0) return `В целом должны вы — по ${groups}.`;
  return "Все расчёты закрыты.";
}

/**
 * Куда ведёт «Погасить долги»: в группу, где вы должны больше всего. Долгов нет —
 * в группу с самым крупным балансом: там разговор о деньгах всё равно ближе всего.
 * Диалог погашения живёт внутри группы и требует её участников, поэтому с общей
 * сводки мы именно переходим в группу, а не открываем его здесь.
 */
function settleTarget(groups: DashboardGroupSummary[]): DashboardGroupSummary | undefined {
  if (groups.length === 0) return undefined;
  const debts = groups.filter((group) => group.net_cents < 0);
  const pool = debts.length > 0 ? debts : groups;
  return pool.reduce((best, group) =>
    Math.abs(group.net_cents) > Math.abs(best.net_cents) ? group : best,
  );
}

/**
 * Куда ведёт «Упростить»: в самую многолюдную группу. Число встречных переводов
 * растёт с числом участников, поэтому упрощение там даёт наибольший выигрыш.
 */
function simplifyTarget(groups: DashboardGroupSummary[]): DashboardGroupSummary | undefined {
  if (groups.length === 0) return undefined;
  return groups.reduce((best, group) =>
    group.member_count > best.member_count ? group : best,
  );
}

function SummarySkeleton() {
  return (
    <div className="grid gap-5 lg:grid-cols-[1.65fr_1fr]">
      <Card className="flex flex-col gap-7 p-5 sm:p-7 lg:p-8">
        <div>
          <Skeleton className="h-3.5 w-36" />
          <Skeleton className="mt-3 h-12 w-64" />
          <Skeleton className="mt-3 h-4 w-52" />
        </div>
        <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
          <Skeleton className="h-[86px] rounded-tile" />
          <Skeleton className="h-[86px] rounded-tile" />
        </div>
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <Skeleton className="h-12 w-full rounded-full sm:w-44" />
          <Skeleton className="h-12 w-full rounded-full sm:w-36" />
        </div>
      </Card>
      <Card className="flex flex-col p-5 sm:p-7 lg:p-8">
        <Skeleton className="h-3.5 w-32" />
        <Skeleton className="mt-3 h-8 w-44" />
        <Skeleton className="mt-2 h-4 w-36" />
        <Skeleton className="mt-auto h-16 w-full rounded-tile" />
      </Card>
    </div>
  );
}

/**
 * Две карточки-героя главной: слева итоговый баланс с действиями, справа — сумма
 * расходов за период с мини-графиком по месяцам.
 */
export function SummaryCards({
  summary,
  isLoading,
  periodLabel = "выбранный период",
  monthly,
  isMonthlyLoading,
  isMonthlyError,
}: SummaryCardsProps) {
  if (isLoading || !summary) return <SummarySkeleton />;

  const currency = summary.currency;
  const groups = summary.groups ?? [];
  const settle = settleTarget(groups);
  const simplify = simplifyTarget(groups);

  return (
    <div className="grid gap-5 lg:grid-cols-[1.65fr_1fr]">
      <Card className="flex min-w-0 flex-col gap-7 p-5 sm:p-7 lg:p-8">
        <div className="min-w-0">
          <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
            Итоговый баланс
          </p>
          <p
            className={cn(
              "tabular-nums-money mt-2.5 text-[40px] font-bold leading-none tracking-[-0.035em] [overflow-wrap:anywhere] lg:text-[60px]",
              summary.net_cents === 0 ? "text-foreground" : balanceToneClass(summary.net_cents),
            )}
          >
            {formatSigned(summary.net_cents, currency)}
          </p>
          <p className="mt-3 text-base text-muted-foreground">
            {netCaption(summary.net_cents, summary.group_count)}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
          <BalanceCard
            label="Вам должны"
            cents={summary.owed_to_you_cents}
            currency={currency}
            marker="positive"
            tone={summary.owed_to_you_cents > 0 ? "positive" : "muted"}
            signed={false}
          />
          <BalanceCard
            label="Вы должны"
            cents={summary.you_owe_cents}
            currency={currency}
            marker="negative"
            tone={summary.you_owe_cents > 0 ? "negative" : "muted"}
            signed={false}
          />
        </div>

        {settle && simplify ? (
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
            <Button asChild className="h-12 w-full sm:w-auto">
              <Link to={`/groups/${settle.group_id}`}>
                <ArrowLeftRight aria-hidden />
                Погасить долги
              </Link>
            </Button>
            <Button asChild variant="secondary" className="h-12 w-full sm:w-auto">
              <Link to={`/groups/${simplify.group_id}`}>
                <Sparkles aria-hidden />
                Упростить
              </Link>
            </Button>
          </div>
        ) : null}
      </Card>

      <Card className="flex min-w-0 flex-col p-5 sm:p-7 lg:p-8">
        <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
          Всего расходов
        </p>
        <p className="tabular-nums-money mt-2.5 text-[28px] font-bold leading-[1.1] tracking-[-0.03em] [overflow-wrap:anywhere] lg:text-[34px]">
          {formatMoney(summary.total_spending_cents, currency)}
        </p>
        <p className="mt-1.5 text-[15px] text-muted-foreground">
          {plural(summary.expense_count, "расход", "расхода", "расходов")} · {periodLabel}
        </p>

        {isMonthlyError ? (
          <p className="mt-auto pt-7 text-[13px] text-dim">
            Не удалось загрузить график по месяцам
          </p>
        ) : (
          <MonthlyMiniChart
            data={monthly}
            isLoading={isMonthlyLoading}
            className="mt-auto pt-7"
          />
        )}
      </Card>
    </div>
  );
}
