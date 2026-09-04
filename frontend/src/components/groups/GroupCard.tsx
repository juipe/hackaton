import { Link } from "react-router-dom";

import { GroupAvatar } from "@/components/common/GroupAvatar";
import { netBalanceCaption } from "@/components/groups/balance-copy";
import { plural } from "@/lib/format";
import {
  balanceToneClass,
  formatMoney,
  formatMoneyRounded,
  formatSigned,
} from "@/lib/money";
import { cn } from "@/lib/utils";
import type { DashboardGroupSummary } from "@/types/api";

/**
 * Одна карточка на два экрана: «Главная» и «Группы» показывают её одинаково,
 * поэтому она принимает не `Group`, а ровно те поля, которые есть в обоих
 * источниках. Сводка дашборда называет их иначе — для неё есть
 * {@link dashboardGroupToCard}.
 */
export interface GroupCardGroup {
  id: string;
  name: string;
  member_count: number;
  my_net_cents: number;
  total_spending_cents: number;
  currency?: string;
}

/** Переводит строку дашборд-сводки в то, что ждёт карточка. */
export function dashboardGroupToCard(group: DashboardGroupSummary): GroupCardGroup {
  return {
    id: group.group_id,
    name: group.name,
    member_count: group.member_count,
    my_net_cents: group.net_cents,
    total_spending_cents: group.total_spending_cents,
    currency: group.currency,
  };
}

export interface GroupCardProps {
  group: GroupCardGroup;
  /**
   * Ваша доля в расходах группы, копейки. Полоса прогресса и подпись под ней
   * рисуются только когда доля известна: выдумывать процент нельзя, а списки
   * групп её пока не отдают.
   */
  shareCents?: number;
  className?: string;
}

export function GroupCard({ group, shareCents, className }: GroupCardProps) {
  const net = group.my_net_cents;
  const total = group.total_spending_cents;
  const showShare = shareCents !== undefined && total > 0;
  const sharePercent = showShare
    ? Math.min(100, Math.max(0, Math.round((shareCents / total) * 100)))
    : 0;

  return (
    <Link
      to={`/groups/${group.id}`}
      className={cn(
        "flex h-full flex-col rounded-panel bg-card p-5 shadow-panel transition-shadow hover:shadow-panelHover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:p-6",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <GroupAvatar group={group} size="md" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-semibold tracking-[-0.01em] text-foreground">
            {group.name}
          </p>
          <p className="mt-0.5 text-[13px] text-dim">
            {plural(group.member_count, "участник", "участника", "участников")}
          </p>
        </div>
      </div>

      <p
        className={cn(
          "mt-[22px] text-[26px] font-bold leading-none tracking-[-0.025em] tabular-nums-money [overflow-wrap:anywhere] sm:text-[30px]",
          net === 0 ? "text-foreground" : balanceToneClass(net),
        )}
      >
        {formatSigned(net, group.currency)}
      </p>
      <p className="mt-1.5 text-sm text-muted-foreground">{netBalanceCaption(net)}</p>

      {showShare ? (
        <div className="mt-auto pt-5">
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${sharePercent}%` }}
            />
          </div>
          <p className="mt-2.5 text-[13px] text-dim">
            Ваша доля — {sharePercent}% от{" "}
            <span className="tabular-nums-money">{formatMoney(total, group.currency)}</span>
          </p>
        </div>
      ) : (
        /*
         * Доля известна не везде: ни список групп, ни сводка дашборда её не
         * считают. Выдумывать процент нельзя, а пустой низ ломал бы высоту
         * карточек — поэтому на месте полосы стоит честная сумма расходов.
         */
        <p className="mt-auto pt-5 text-[13px] text-dim tabular-nums-money">
          Расходы группы — {formatMoneyRounded(total)}
        </p>
      )}
    </Link>
  );
}
