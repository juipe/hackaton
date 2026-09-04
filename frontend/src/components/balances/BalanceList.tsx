import { useMemo } from "react";
import { Users } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { UserAvatar } from "@/components/common/UserAvatar";
import { memberBalanceState } from "@/components/groups/balance-copy";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { UserBalance } from "@/types/api";

export interface BalanceListProps {
  balances: UserBalance[];
  currency: string;
  currentUserId: string;
  className?: string;
}

function amountToneClass(cents: number): string {
  if (cents > 0) return "text-positive";
  if (cents < 0) return "text-negative";
  return "text-dim";
}

export function BalanceList({
  balances,
  currency,
  currentUserId,
  className,
}: BalanceListProps) {
  // The reader is looking for themselves first, then for whoever is furthest
  // from square, so that is the order the rows are put in.
  const ordered = useMemo(
    () =>
      [...balances].sort((a, b) => {
        if (a.user_id === currentUserId) return -1;
        if (b.user_id === currentUserId) return 1;
        return b.net_cents - a.net_cents || a.user.name.localeCompare(b.user.name);
      }),
    [balances, currentUserId],
  );

  if (ordered.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="Балансов пока нет"
        description="Как только появится первый расход, здесь будет видно, кто платил, какая у кого доля и кто сейчас в плюсе."
        className={className}
      />
    );
  }

  return (
    <ul className={cn("flex flex-col gap-1.5", className)}>
      {ordered.map((balance) => {
        const isMe = balance.user_id === currentUserId;
        const copy = memberBalanceState(balance.net_cents, balance.user.name, isMe);
        // Знак уже сказан словами («в минусе»), поэтому у числа его нет.
        const amount = formatMoney(Math.abs(balance.net_cents), currency);

        return (
          <li
            key={balance.user_id}
            className={cn(
              "flex items-center gap-3 rounded-row px-3.5 py-3 transition-colors sm:gap-3.5 sm:px-[18px] sm:py-3.5",
              isMe ? "bg-accent" : "hover:bg-subtle",
            )}
          >
            <UserAvatar
              user={balance.user}
              size="lg"
              fallbackClassName={isMe ? "bg-card text-accent-foreground" : undefined}
            />

            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] sm:text-base">
                <span className={cn(isMe ? "font-bold" : "font-semibold", "text-foreground")}>
                  {copy.subject}
                </span>
                <span className={isMe ? "text-[#4E7A58]" : "text-dim"}> {copy.state}</span>
              </p>
              <p
                className={cn(
                  "whitespace-normal text-[13px] tabular-nums-money sm:truncate",
                  isMe ? "text-[#4E7A58]" : "text-dim",
                )}
              >
                Оплачено {formatMoney(balance.paid_cents, currency)} · Доля{" "}
                {formatMoney(balance.owed_cents, currency)}
              </p>
            </div>

            <p
              className={cn(
                "shrink-0 text-[17px] font-bold tracking-[-0.02em] tabular-nums-money sm:text-[19px]",
                amountToneClass(balance.net_cents),
              )}
            >
              {amount}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
