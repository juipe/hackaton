import { ArrowRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { CategoryChart } from "@/components/charts/CategoryChart";
import { ActivityFeed } from "@/components/common/ActivityFeed";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { FirstRunCard } from "@/components/dashboard/FirstRunCard";
import { GroupsOverview } from "@/components/dashboard/GroupsOverview";
import { PeriodFilter } from "@/components/dashboard/PeriodFilter";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { Card } from "@/components/ui/card";
import { useRecentActivity } from "@/hooks/useActivity";
import { useCurrentUser } from "@/hooks/useAuth";
import {
  useDashboardSummary,
  useSpendingByCategory,
  useSpendingOverTime,
} from "@/hooks/useDashboard";
import { DEFAULT_CURRENCY } from "@/lib/money";
import type { DashboardParams, DashboardPeriod } from "@/types/api";

function greetingPrefix(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Доброе утро";
  if (hour < 18) return "Добрый день";
  return "Добрый вечер";
}

function firstNameOf(name: string): string {
  const [first] = name.trim().split(/\s+/);
  return first || name;
}

function periodLabelFor(period: DashboardPeriod): string {
  switch (period) {
    case "this_month":
      return "за этот месяц";
    case "last_month":
      return "за прошлый месяц";
    case "last_3_months":
      return "за последние 3 месяца";
    case "custom":
      return "за выбранный период";
    default:
      return "за всё время";
  }
}

export default function DashboardPage() {
  const user = useCurrentUser();
  const [params, setParams] = useState<DashboardParams>({ period: "all" });

  const summaryQuery = useDashboardSummary(params);
  const categoryQuery = useSpendingByCategory(params);
  const timeQuery = useSpendingOverTime(params);
  const activityQuery = useRecentActivity(10);

  const summary = summaryQuery.data;
  const currency = summary?.currency ?? DEFAULT_CURRENCY;
  const periodLabel = periodLabelFor(params.period ?? "all");
  const rangeIncomplete =
    params.period === "custom" && (!params.date_from || !params.date_to);

  let body: ReactNode;

  if (rangeIncomplete) {
    body = (
      <Card className="p-5 text-center sm:p-8">
        <p className="text-[15px] text-muted-foreground">
          Выберите начало и конец периода, чтобы увидеть цифры.
        </p>
      </Card>
    );
  } else if (summaryQuery.isError) {
    body = (
      <ErrorState error={summaryQuery.error} onRetry={() => void summaryQuery.refetch()} />
    );
  } else if (summary !== undefined && summary.group_count === 0) {
    // A brand-new account has nothing to total up, so four zeroes and two blank
    // charts would only teach the user that the product looks broken.
    body = <FirstRunCard firstName={firstNameOf(user.name)} />;
  } else {
    body = (
      <>
        <SummaryCards
          summary={summary}
          isLoading={summaryQuery.isLoading}
          periodLabel={periodLabel}
          monthly={timeQuery.data}
          isMonthlyLoading={timeQuery.isLoading}
          isMonthlyError={timeQuery.isError}
        />

        <div className="flex items-baseline justify-between gap-4 px-1 pt-2">
          <h2 className="text-[20px] font-bold tracking-[-0.02em]">Ваши группы</h2>
          <Link
            to="/groups"
            className="inline-flex shrink-0 items-center gap-1.5 text-[15px] font-semibold text-accent-foreground hover:underline"
          >
            Все группы
            <ArrowRight className="size-[15px]" aria-hidden />
          </Link>
        </div>

        <GroupsOverview groups={summary?.groups} isLoading={summaryQuery.isLoading} />

        <div className="grid items-start gap-5 lg:grid-cols-2">
          <SectionCard
            className="min-w-0"
            title="Куда ушли деньги"
            description={`Все группы · ${periodLabel}`}
            descriptionClassName="text-dim"
          >
            {categoryQuery.isError ? (
              <ErrorState
                error={categoryQuery.error}
                onRetry={() => void categoryQuery.refetch()}
              />
            ) : (
              <CategoryChart
                data={categoryQuery.data}
                currency={currency}
                isLoading={categoryQuery.isLoading}
              />
            )}
          </SectionCard>

          <SectionCard
            className="min-w-0"
            title="Последние события"
            description="Что происходило во всех ваших группах"
            descriptionClassName="text-dim"
          >
            <ActivityFeed
              activities={activityQuery.data}
              isLoading={activityQuery.isLoading}
              error={activityQuery.error}
              showGroup
              emptyLabel="Пока ничего не происходило"
            />
          </SectionCard>
        </div>
      </>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <PageHeader
        title="Главная"
        description={`${greetingPrefix()}, ${firstNameOf(user.name)}`}
        actions={<PeriodFilter value={params} onChange={setParams} />}
      />
      {body}
    </div>
  );
}
