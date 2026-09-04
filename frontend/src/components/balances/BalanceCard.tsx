import { formatMoney, formatSigned } from "@/lib/money";
import { cn } from "@/lib/utils";

/**
 * `muted` — нулевая плитка со знаковой подписью: «Вы должны 0,00 ₽» красным
 * тревожит на пустом месте, поэтому ноль там гасится.
 */
export type BalanceTone = "auto" | "positive" | "negative" | "neutral" | "muted";

export interface BalanceCardProps {
  label: string;
  cents: number;
  currency: string;
  hint?: string;
  tone?: BalanceTone;
  /**
   * Точка-маркер слева от подписи. Нужна там, где две плитки стоят рядом и
   * различаются только знаком («Вам должны» / «Вы должны»); в плитках с
   * нейтральным числом она была бы украшением без смысла.
   */
  marker?: "positive" | "negative";
  /**
   * Only an "auto" tile is showing a signed net figure, where the +/- is the
   * whole point. A tile with a fixed tone already says in words which side of
   * the ledger it is on, so a sign there would just be noise.
   */
  signed?: boolean;
  className?: string;
}

const TONE: Record<BalanceTone, string> = {
  auto: "",
  positive: "text-positive",
  negative: "text-negative",
  neutral: "text-foreground",
  muted: "text-muted-foreground",
};

const MARKER: Record<"positive" | "negative", string> = {
  positive: "bg-primary",
  negative: "bg-negative",
};

/** Плитка внутри карточки баланса: подпись, число 24px и необязательная сноска. */
export function BalanceCard({
  label,
  cents,
  currency,
  hint,
  tone = "auto",
  marker,
  signed,
  className,
}: BalanceCardProps) {
  const amountClass =
    tone === "auto"
      ? cents > 0
        ? TONE.positive
        : cents < 0
          ? TONE.negative
          : TONE.neutral
      : TONE[tone];
  const withSign = signed ?? tone === "auto";
  const amount = withSign ? formatSigned(cents, currency) : formatMoney(cents, currency);

  return (
    <div className={cn("rounded-tile bg-secondary px-4 py-3.5 sm:px-5 sm:py-4", className)}>
      <p className="flex items-center gap-2 text-sm leading-snug text-muted-foreground">
        {marker ? (
          <span
            aria-hidden="true"
            className={cn("size-2 shrink-0 rounded-full", MARKER[marker])}
          />
        ) : null}
        <span className="min-w-0">{label}</span>
      </p>

      <p
        className={cn(
          // Никакого переноса: сумма, разорванная посреди цифр («383 340,0» и
          // «0 ₽» на следующей строке), читается как другое число. Плитки в
          // узком экране встают в колонку, поэтому места хватает.
          "mt-1.5 whitespace-nowrap text-[22px] font-bold tracking-[-0.02em] tabular-nums-money sm:text-2xl",
          amountClass,
        )}
      >
        {amount}
      </p>

      {hint ? <p className="mt-1 text-[13px] text-dim">{hint}</p> : null}
    </div>
  );
}
