import { DEFAULT_CURRENCY, balanceToneClass, formatMoney, formatSigned } from "@/lib/money";
import { cn } from "@/lib/utils";

export interface MoneyProps {
  cents: number;
  /** Kept for call-site compatibility; the app has exactly one currency. */
  currency?: string;
  /** Credits get an explicit `+`. Use for balances, not for raw expense amounts. */
  signed?: boolean;
  /** Tinted by sign via `balanceToneClass`. Turn it off where the number is not a balance. */
  tone?: boolean;
  className?: string;
}

export function Money({
  cents,
  currency = DEFAULT_CURRENCY,
  signed = false,
  tone = true,
  className,
}: MoneyProps) {
  const text = signed ? formatSigned(cents, currency) : formatMoney(cents, currency);
  return (
    <span className={cn("tabular-nums-money", tone && balanceToneClass(cents), className)}>
      {text}
    </span>
  );
}
