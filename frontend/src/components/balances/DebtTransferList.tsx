import { ShieldCheck } from "lucide-react";

import { AvatarStack } from "@/components/common/AvatarStack";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Transfer } from "@/types/api";

export interface DebtTransferListProps {
  transfers: Transfer[];
  currency: string;
  currentUserId: string;
  onSettle?: (transfer: Transfer) => void;
  emptyLabel?: string;
  className?: string;
}

type Side = "mine-out" | "mine-in" | "theirs";

interface RowCopy {
  payer: string;
  /**
   * The direction marker between the two names. An arrow rather than a verb:
   * a Russian phrase like "X owes Y" would need the second name in the dative,
   * and the app never inflects the names people typed in themselves.
   */
  verb: string;
  payee: string;
  side: Side;
  amountClass: string;
  /** Подпись кнопки: свой долг платят, чужой — отмечают погашенным. */
  action: string;
  sentence: string;
}

const ARROW = "→";

/** Both sides of a debt are always named in the nominative, either side of `→`. */
function rowCopy(transfer: Transfer, currentUserId: string): RowCopy {
  const from = transfer.from_user.name;
  const to = transfer.to_user.name;

  if (transfer.from_user_id === currentUserId) {
    return {
      payer: "Вы",
      verb: ARROW,
      payee: to,
      side: "mine-out",
      amountClass: "text-negative",
      action: "Рассчитаться",
      sentence: `Вы ${ARROW} ${to}`,
    };
  }

  if (transfer.to_user_id === currentUserId) {
    return {
      payer: from,
      verb: ARROW,
      payee: "вы",
      side: "mine-in",
      amountClass: "text-positive",
      action: "Погасить",
      sentence: `${from} ${ARROW} вы`,
    };
  }

  // Between two other people the amount is neither a credit nor a debt for the
  // reader, so it stays neutral — green and red only ever mean "your side".
  return {
    payer: from,
    verb: ARROW,
    payee: to,
    side: "theirs",
    amountClass: "text-foreground",
    action: "Погасить",
    sentence: `${from} ${ARROW} ${to}`,
  };
}

const BUTTON_VARIANT = {
  "mine-out": "default",
  "mine-in": "soft",
  theirs: "muted",
} as const;

export function DebtTransferList({
  transfers,
  currency,
  currentUserId,
  onSettle,
  emptyLabel,
  className,
}: DebtTransferListProps) {
  if (transfers.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title={emptyLabel ?? "Все в расчёте"}
        description="Непогашенных долгов нет."
        className={className}
      />
    );
  }

  return (
    <ul className={cn("flex flex-col gap-2.5", className)}>
      {transfers.map((transfer) => {
        const copy = rowCopy(transfer, currentUserId);
        const amount = formatMoney(transfer.amount_cents, currency);

        return (
          <li
            key={`${transfer.from_user_id}-${transfer.to_user_id}`}
            className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-row bg-subtle px-4 py-3.5 transition-colors hover:bg-subtle-hover sm:px-[18px]"
          >
            {/* Кольцо аватаров совпадает с фоном строки — иначе нахлёст грязнит. */}
            <AvatarStack
              users={[transfer.from_user, transfer.to_user]}
              size="md"
              max={2}
              ringClassName="shadow-[0_0_0_3px_hsl(var(--subtle))]"
            />

            <p className="min-w-0 flex-1 basis-28 text-[15px] font-semibold tracking-[-0.01em] sm:text-base">
              <span className="text-foreground">{copy.payer}</span>
              <span className="font-medium text-dim"> {copy.verb} </span>
              <span className="text-foreground">{copy.payee}</span>
            </p>

            <p
              className={cn(
                "ml-auto shrink-0 text-[17px] font-bold tracking-[-0.02em] tabular-nums-money sm:text-[19px]",
                copy.amountClass,
              )}
            >
              {amount}
            </p>

            {onSettle ? (
              <Button
                type="button"
                variant={BUTTON_VARIANT[copy.side]}
                size="sm"
                className="shrink-0 px-5 font-bold"
                onClick={() => onSettle(transfer)}
                aria-label={`${copy.action}: ${copy.sentence}, ${amount}`}
              >
                {copy.action}
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
