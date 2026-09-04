import { useState } from "react";
import {
  ArrowLeft,
  ArrowLeftRight,
  Banknote,
  BarChart3,
  ListChecks,
  Scale,
  Sparkles,
} from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { BalanceCard } from "@/components/balances/BalanceCard";
import { BalanceList } from "@/components/balances/BalanceList";
import { DebtTransferList } from "@/components/balances/DebtTransferList";
import { PaymentList } from "@/components/balances/PaymentList";
import { SettleUpModal } from "@/components/balances/SettleUpModal";
import { SimplifyDebtsDialog } from "@/components/balances/SimplifyDebtsDialog";
import { BalanceBarChart } from "@/components/charts/BalanceBarChart";
import { CategoryChart } from "@/components/charts/CategoryChart";
import { MonthlySpendChart } from "@/components/charts/MonthlySpendChart";
import { ActivityFeed } from "@/components/common/ActivityFeed";
import { AvatarStack } from "@/components/common/AvatarStack";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { SectionCard } from "@/components/common/SectionCard";
import { SavingTipsCard } from "@/components/dashboard/SavingTipsCard";
import { AddExpenseDialog } from "@/components/expenses/AddExpenseDialog";
import { ExpenseList } from "@/components/expenses/ExpenseList";
import { VoiceExpenseDialog } from "@/components/expenses/VoiceExpenseDialog";
import {
  groupBalanceExplainer,
  transferCountCaption,
} from "@/components/groups/balance-copy";
import { GroupSummaryHeader } from "@/components/groups/GroupSummaryHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGroupActivity } from "@/hooks/useActivity";
import { useCurrentUser } from "@/hooks/useAuth";
import { useBalances } from "@/hooks/useBalances";
import { useCategories } from "@/hooks/useCategories";
import { useSpendingByCategory, useSpendingOverTime } from "@/hooks/useDashboard";
import { useExpenses } from "@/hooks/useExpenses";
import { useGroup, useMembers } from "@/hooks/useGroups";
import { usePayments } from "@/hooks/usePayments";
import { ApiError } from "@/lib/api";
import { joinNames, plural } from "@/lib/format";
import { DEFAULT_CURRENCY, formatMoney, formatSigned } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Transfer } from "@/types/api";

const TAB_VALUES = ["balances", "expenses", "analytics", "activity"] as const;
type TabValue = (typeof TAB_VALUES)[number];

/** Сколько имён показать под стопкой аватаров, прежде чем свернуть в «и ещё N». */
const MEMBERS_SHOWN = 3;

function isTabValue(value: string | null): value is TabValue {
  return value !== null && (TAB_VALUES as readonly string[]).includes(value);
}

function heroToneClass(cents: number): string {
  if (cents > 0) return "text-positive";
  if (cents < 0) return "text-negative";
  return "text-foreground";
}

interface SettlePrefill {
  fromUserId?: string;
  toUserId?: string;
  amountCents?: number;
}

/** Надзаголовок карточки — капсом, мелко, приглушённо. */
function Eyebrow({ children }: { children: string }) {
  return (
    <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
      {children}
    </p>
  );
}

/** Обёртка для ошибки внутри блока страницы — в том же языке, что карточки. */
function ErrorCard({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Card className="p-5 sm:p-7">
      <ErrorState error={error} onRetry={onRetry} />
    </Card>
  );
}

/** A dead end for this group — wrong link, deleted group, or someone else's group. */
function GroupUnavailable({
  error,
  hint,
  onRetry,
}: {
  error: unknown;
  hint?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="py-10">
      <Card className="mx-auto max-w-md p-5 sm:p-8">
        <ErrorState error={error} onRetry={onRetry} />
        {hint ? (
          <p className="mt-3 text-center text-sm text-muted-foreground">{hint}</p>
        ) : null}
        <div className="mt-5 flex justify-center">
          <Button asChild variant="outline">
            <Link to="/groups">
              <ArrowLeft />
              К списку групп
            </Link>
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const id = groupId ?? "";
  const currentUser = useCurrentUser();
  const [searchParams, setSearchParams] = useSearchParams();

  const [addOpen, setAddOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [settleOpen, setSettleOpen] = useState(false);
  const [simplifyOpen, setSimplifyOpen] = useState(false);
  const [settlePrefill, setSettlePrefill] = useState<SettlePrefill | undefined>(undefined);
  const [showSimplified, setShowSimplified] = useState(false);

  const groupQuery = useGroup(id);
  const membersQuery = useMembers(id);
  const balancesQuery = useBalances(id);
  const categoriesQuery = useCategories();
  const activityQuery = useGroupActivity(id, 30);
  const paymentsQuery = usePayments(id);
  // Only the server's `total` is wanted here, so ask for the smallest page possible.
  const expenseCountQuery = useExpenses(id, { limit: 1 });
  const categorySpendQuery = useSpendingByCategory({ period: "all", group_id: id });
  const overTimeQuery = useSpendingOverTime({ period: "all", group_id: id });

  const group = groupQuery.data;
  const balances = balancesQuery.data;
  const members = membersQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];
  const currency = group?.currency ?? balances?.currency ?? DEFAULT_CURRENCY;

  const tabParam = searchParams.get("tab");
  const tab: TabValue = isTabValue(tabParam) ? tabParam : "balances";

  const handleTabChange = (value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "balances") next.delete("tab");
    else next.set("tab", value);
    setSearchParams(next, { replace: true });
  };

  const openSettle = (transfer?: Transfer) => {
    setSettlePrefill(
      transfer
        ? {
            fromUserId: transfer.from_user_id,
            toUserId: transfer.to_user_id,
            amountCents: transfer.amount_cents,
          }
        : undefined,
    );
    setSettleOpen(true);
  };

  if (!groupId) {
    return (
      <GroupUnavailable
        error={new Error("Эта ссылка не ведёт ни на одну группу")}
        hint="Выберите группу из списка, чтобы продолжить."
      />
    );
  }

  if (groupQuery.isPending) {
    return <LoadingState label="Загружаем группу…" className="py-20" />;
  }

  if (groupQuery.isError || !group) {
    const status = groupQuery.error instanceof ApiError ? groupQuery.error.status : 0;
    if (status === 403) {
      return (
        <GroupUnavailable
          error={groupQuery.error}
          hint="Открыть группу могут только её участники. Попросите кого-нибудь из них прислать вам приглашение."
        />
      );
    }
    if (status === 404) {
      return (
        <GroupUnavailable
          error={groupQuery.error}
          hint="Группа удалена, либо адрес устарел."
        />
      );
    }
    return (
      <GroupUnavailable
        error={groupQuery.error}
        onRetry={() => void groupQuery.refetch()}
      />
    );
  }

  const pairwiseCount = balances?.pairwise.length ?? 0;
  const simplifiedCount = balances?.simplified.length ?? 0;
  const transfers = showSimplified ? (balances?.simplified ?? []) : (balances?.pairwise ?? []);

  // The group payload already carries both figures, so the hero is correct while
  // the (heavier) balances query is still in flight and simply sharpens afterwards.
  const myNet = balances?.me.net_cents ?? group.my_net_cents;
  const totalSpending = balances?.total_spending_cents ?? group.total_spending_cents;
  const myShare = balances?.me.owed_cents ?? 0;
  const expenseCount = expenseCountQuery.data?.total ?? 0;
  // Доля считается только когда есть от чего её считать — придумывать 0% не надо.
  const sharePercent =
    totalSpending > 0 ? Math.round((myShare / totalSpending) * 100) : null;
  const memberUsers = members.map((member) => member.user);

  return (
    <div className="flex flex-col gap-6 pb-2">
      <Link
        to="/groups"
        className="inline-flex w-fit items-center gap-2 rounded-full bg-card py-2 pl-3 pr-4 text-sm font-semibold text-muted-foreground shadow-flat transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4 shrink-0" aria-hidden="true" />
        Все группы
      </Link>

      <GroupSummaryHeader
        group={group}
        onAddExpense={() => setAddOpen(true)}
        onVoiceExpense={() => setVoiceOpen(true)}
      />

      {balancesQuery.isError && !balances ? (
        <ErrorCard
          error={balancesQuery.error}
          onRetry={() => void balancesQuery.refetch()}
        />
      ) : balancesQuery.isPending ? (
        <div className="grid gap-5 lg:grid-cols-[1.65fr_1fr]">
          <Skeleton className="h-[300px] rounded-card" />
          <Skeleton className="h-[300px] rounded-card" />
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1.65fr_1fr]">
          <Card className="flex min-w-0 flex-col gap-6 p-5 sm:p-7 lg:gap-7 lg:p-8">
            <div>
              <Eyebrow>Ваш баланс в группе</Eyebrow>
              <p
                className={cn(
                  "mt-2.5 break-words text-[40px] font-bold leading-none tracking-[-0.035em] tabular-nums-money lg:text-[60px]",
                  heroToneClass(myNet),
                )}
              >
                {formatSigned(myNet, currency)}
              </p>
              <p className="mt-3 text-base text-muted-foreground">
                {groupBalanceExplainer(myNet, pairwiseCount, simplifiedCount)}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
              <BalanceCard
                label="Вы заплатили"
                cents={balances?.me.paid_cents ?? 0}
                currency={currency}
                tone="neutral"
              />
              <BalanceCard
                label="Ваша доля"
                cents={myShare}
                currency={currency}
                tone="neutral"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <Button
                className="h-12 flex-1 sm:flex-none"
                onClick={() => openSettle()}
              >
                <ArrowLeftRight />
                Погасить долг
              </Button>
              <Button
                variant="secondary"
                className="h-12 flex-1 sm:flex-none"
                onClick={() => setSimplifyOpen(true)}
              >
                <Sparkles />
                Упростить долги
              </Button>
            </div>
          </Card>

          <Card className="flex min-w-0 flex-col p-5 sm:p-7 lg:p-8">
            <Eyebrow>Расходы группы</Eyebrow>
            <p className="mt-2.5 break-words text-[28px] font-bold leading-[1.1] tracking-[-0.03em] tabular-nums-money lg:text-[34px]">
              {formatMoney(totalSpending, currency)}
            </p>
            <p className="mt-1.5 text-[15px] text-muted-foreground">
              {plural(expenseCount, "расход", "расхода", "расходов")} · за всё время
            </p>

            <div className="mt-auto pt-7">
              {sharePercent !== null ? (
                <>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.min(100, sharePercent)}%` }}
                    />
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Ваша доля —{" "}
                    <span className="font-semibold text-foreground tabular-nums-money">
                      {sharePercent}%
                    </span>{" "}
                    от всех расходов
                  </p>
                </>
              ) : null}

              {memberUsers.length > 0 ? (
                <div className="mt-5 flex items-center gap-2.5">
                  <AvatarStack users={memberUsers} size="sm" max={MEMBERS_SHOWN} />
                  <span className="min-w-0 truncate text-sm text-dim">
                    {joinNames(
                      memberUsers.map((user) => user.name),
                      MEMBERS_SHOWN,
                    )}
                  </span>
                </div>
              ) : null}
            </div>
          </Card>
        </div>
      )}

      <Tabs value={tab} onValueChange={handleTabChange}>
        <div className="no-scrollbar -my-1 snap-x snap-mandatory overflow-x-auto scroll-px-4 py-1">
          <TabsList className="w-max">
            <TabsTrigger value="balances" className="snap-start">
              <Scale aria-hidden="true" />
              Балансы
            </TabsTrigger>
            <TabsTrigger value="expenses" className="snap-start">
              <Banknote aria-hidden="true" />
              Расходы
            </TabsTrigger>
            <TabsTrigger value="analytics" className="snap-start">
              <BarChart3 aria-hidden="true" />
              Аналитика
            </TabsTrigger>
            <TabsTrigger value="activity" className="snap-start">
              <ListChecks aria-hidden="true" />
              События
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="balances" className="flex flex-col gap-5">
          {balancesQuery.isPending ? (
            <LoadingState label="Считаем, кто кому должен…" />
          ) : balancesQuery.isError || !balances ? (
            <ErrorCard
              error={balancesQuery.error}
              onRetry={() => void balancesQuery.refetch()}
            />
          ) : (
            <div className="grid items-start gap-5 lg:grid-cols-[1.15fr_1fr]">
              <SectionCard
                titleClassName="text-[20px]"
                className="min-w-0"
                title="Кто кому должен"
                description={
                  showSimplified
                    ? "Минимум переводов, которые закрывают всё. Итоговый баланс ни у кого не меняется — меняется только маршрут денег."
                    : "Все долги ровно так, как их создали расходы, — взаимозачётом внутри каждой пары."
                }
                action={
                  <div className="flex shrink-0 items-center gap-2.5">
                    <Label
                      htmlFor="simplify-debts"
                      className="whitespace-nowrap text-[13px] font-semibold text-muted-foreground"
                    >
                      Упростить
                    </Label>
                    <Switch
                      id="simplify-debts"
                      checked={showSimplified}
                      onCheckedChange={setShowSimplified}
                    />
                  </div>
                }
              >
                <p className="mb-3.5 text-[13px] text-dim">
                  {transferCountCaption(pairwiseCount, simplifiedCount)}
                </p>
                <DebtTransferList
                  transfers={transfers}
                  currency={currency}
                  currentUserId={currentUser.id}
                  onSettle={openSettle}
                />
              </SectionCard>

              <SectionCard
                titleClassName="text-[20px]"
                className="min-w-0"
                title="Балансы участников"
                description="Положительное число значит, что группа должна этому человеку."
              >
                <BalanceList
                  balances={balances.balances}
                  currency={currency}
                  currentUserId={currentUser.id}
                />
              </SectionCard>
            </div>
          )}

          {/*
            Переводы — вторая половина истории денег в группе: долги выше
            показывают, что осталось, эта карточка — что уже закрыли.
          */}
          <SectionCard
            className="min-w-0"
            title="Переводы"
            description="Расчёты, которые участники уже записали, — от самого свежего."
          >
            {paymentsQuery.isPending ? (
              <LoadingState label="Загружаем переводы…" />
            ) : paymentsQuery.isError ? (
              <ErrorState
                error={paymentsQuery.error}
                onRetry={() => void paymentsQuery.refetch()}
              />
            ) : (
              <PaymentList
                payments={paymentsQuery.data}
                currency={currency}
                currentUserId={currentUser.id}
              />
            )}
          </SectionCard>
        </TabsContent>

        <TabsContent value="expenses">
          {membersQuery.isPending || categoriesQuery.isPending ? (
            <LoadingState label="Загружаем расходы…" />
          ) : membersQuery.isError || categoriesQuery.isError ? (
            <ErrorCard
              error={membersQuery.error ?? categoriesQuery.error}
              onRetry={() => {
                void membersQuery.refetch();
                void categoriesQuery.refetch();
              }}
            />
          ) : (
            <ExpenseList
              groupId={group.id}
              members={members}
              categories={categories}
              currentUserId={currentUser.id}
            />
          )}
        </TabsContent>

        <TabsContent value="analytics" className="flex flex-col gap-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <SectionCard
              titleClassName="text-[20px]"
              className="min-w-0"
              title="Куда ушли деньги"
              description="Все расходы группы · за всё время"
            >
              {categorySpendQuery.isError ? (
                <ErrorState
                  error={categorySpendQuery.error}
                  onRetry={() => void categorySpendQuery.refetch()}
                />
              ) : (
                <CategoryChart
                  data={categorySpendQuery.data}
                  currency={currency}
                  isLoading={categorySpendQuery.isPending}
                />
              )}
            </SectionCard>

            <SectionCard
              titleClassName="text-[20px]"
              className="min-w-0"
              title="Расходы по месяцам"
              description="Расходы группы месяц за месяцем."
            >
              {overTimeQuery.isError ? (
                <ErrorState
                  error={overTimeQuery.error}
                  onRetry={() => void overTimeQuery.refetch()}
                />
              ) : (
                <MonthlySpendChart
                  data={overTimeQuery.data}
                  currency={currency}
                  isLoading={overTimeQuery.isPending}
                />
              )}
            </SectionCard>
          </div>

          <SavingTipsCard params={{ period: "all", group_id: id }} />

          <SectionCard
            titleClassName="text-[20px]"
            title="Баланс по участникам"
            description="Выше нуля — деньги, которые должны человеку, ниже — те, что должен он."
          >
            {balancesQuery.isError ? (
              <ErrorState
                error={balancesQuery.error}
                onRetry={() => void balancesQuery.refetch()}
              />
            ) : (
              <BalanceBarChart
                balances={balances?.balances}
                currency={currency}
                currentUserId={currentUser.id}
                isLoading={balancesQuery.isPending}
              />
            )}
          </SectionCard>
        </TabsContent>

        <TabsContent value="activity">
          <SectionCard
            titleClassName="text-[20px]"
            title="Последние события"
            description="Все изменения, которые вносили в этой группе."
          >
            <ActivityFeed
              activities={activityQuery.data}
              isLoading={activityQuery.isPending}
              error={activityQuery.error}
              emptyLabel="Пока ничего не происходило"
            />
          </SectionCard>
        </TabsContent>
      </Tabs>

      <AddExpenseDialog open={addOpen} onOpenChange={setAddOpen} groupId={group.id} />
      <VoiceExpenseDialog open={voiceOpen} onOpenChange={setVoiceOpen} groupId={group.id} />
      <SettleUpModal
        open={settleOpen}
        onOpenChange={setSettleOpen}
        group={group}
        members={members}
        balances={balances}
        prefill={settlePrefill}
      />
      <SimplifyDebtsDialog
        open={simplifyOpen}
        onOpenChange={setSimplifyOpen}
        group={group}
        currentUserId={currentUser.id}
      />
    </div>
  );
}
