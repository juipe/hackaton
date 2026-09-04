import { ArrowLeftRight } from "lucide-react";

import { AvatarStack } from "@/components/common/AvatarStack";
import { EmptyState } from "@/components/common/EmptyState";
import { formatDate } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Payment } from "@/types/api";

export interface PaymentListProps {
  payments: Payment[];
  currency: string;
  currentUserId: string;
  className?: string;
}

const ARROW = "→";

/**
 * Обе стороны перевода называются в именительном по разные стороны стрелки —
 * тот же приём, что и в списке долгов: имена, которые люди ввели сами,
 * приложение не склоняет.
 */
function names(payment: Payment, currentUserId: string): { from: string; to: string } {
  return {
    from: payment.from_user_id === currentUserId ? "Вы" : payment.from_user.name,
    to: payment.to_user_id === currentUserId ? "вы" : payment.to_user.name,
  };
}

/**
 * История переводов группы: что уже погашено. Долги живут выше, здесь — только
 * состоявшиеся платежи, поэтому суммы нейтральные: знака у закрытого перевода нет.
 */
export function PaymentList({
  payments,
  currency,
  currentUserId,
  className,
}: PaymentListProps) {
  if (payments.length === 0) {
    return (
      <EmptyState
        icon={ArrowLeftRight}
        title="Переводов пока не было"
        description="Здесь появятся расчёты между участниками, как только кто-нибудь погасит долг."
        className={className}
      />
    );
  }

  return (
    <ul className={cn("flex flex-col gap-2.5", className)}>
      {payments.map((payment) => {
        const copy = names(payment, currentUserId);
        const note = payment.note?.trim();

        return (
          <li
            key={payment.id}
            className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-row bg-subtle px-4 py-3.5 transition-colors hover:bg-subtle-hover sm:px-[18px]"
          >
            {/* Кольцо аватаров совпадает с фоном строки — иначе нахлёст грязнит. */}
            <AvatarStack
              users={[payment.from_user, payment.to_user]}
              size="md"
              max={2}
              ringClassName="shadow-[0_0_0_3px_hsl(var(--subtle))]"
            />

            <div className="min-w-0 flex-1 basis-40">
              <p className="text-[15px] font-semibold tracking-[-0.01em] sm:text-base">
                <span className="text-foreground">{copy.from}</span>
                <span className="font-medium text-dim"> {ARROW} </span>
                <span className="text-foreground">{copy.to}</span>
              </p>
              <p className="mt-0.5 truncate text-[13px] text-dim">
                {formatDate(payment.paid_at)}
                {note ? ` · ${note}` : ""}
              </p>
            </div>

            <p className="tabular-nums-money ml-auto shrink-0 text-[17px] font-bold tracking-[-0.02em] text-foreground sm:text-[19px]">
              {formatMoney(payment.amount_cents, currency)}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
