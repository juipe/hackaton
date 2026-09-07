import { Lightbulb, Loader2, PiggyBank, RotateCw, Sparkles } from "lucide-react";

import { ErrorState } from "@/components/common/ErrorState";
import { SectionCard } from "@/components/common/SectionCard";
import { Button } from "@/components/ui/button";
import { useGenerateSavingTips } from "@/hooks/useDashboard";
import { formatMoneyRounded } from "@/lib/money";
import type { DashboardParams, PotentialSavings, SavingTip } from "@/types/api";

function InitialState({ onGenerate }: { onGenerate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-row bg-subtle px-5 py-9 text-center sm:px-6 sm:py-10">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-accent-foreground">
        <Sparkles className="size-6" aria-hidden />
      </span>
      <p className="mx-auto max-w-[42ch] text-[15px] leading-relaxed text-muted-foreground">
        Твой AI помощник разберёт расходы за выбранный период и предложит пару советов,
        как сократить траты.
      </p>
      <Button type="button" size="sm" onClick={onGenerate}>
        <Sparkles aria-hidden />
        Сгенерировать советы
      </Button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-row bg-subtle px-5 py-9 text-center sm:px-6 sm:py-10">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground">
        <Loader2 className="size-6 animate-spin" aria-hidden />
      </span>
      <p className="text-[15px] font-semibold text-foreground">Анализируем расходы…</p>
      <p className="max-w-[36ch] text-[13px] text-dim">
        Твой AI помощник обрабатывает запрос — это может занять немного времени.
      </p>
    </div>
  );
}

function TipRow({ tip }: { tip: SavingTip }) {
  return (
    <li className="flex items-start gap-3.5 rounded-tile p-3">
      <span className="flex size-[38px] shrink-0 items-center justify-center rounded-chip bg-accent text-accent-foreground">
        <Lightbulb className="size-[18px]" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-semibold leading-[1.4] text-foreground [overflow-wrap:anywhere]">
          {tip.title}
        </p>
        <p className="mt-[3px] text-[13px] leading-[1.4] text-dim [overflow-wrap:anywhere]">
          {tip.text}
        </p>
      </div>
    </li>
  );
}

/**
 * «Можно сэкономить до X» — сумма личных трат по необязательным категориям.
 * Числа считает бэкенд, не модель, поэтому блок показывается и с fallback-советами.
 */
function PotentialSavingsBlock({ savings }: { savings: PotentialSavings }) {
  const breakdown = savings.items
    .map((item) => `${item.name} ${formatMoneyRounded(item.amount_cents)}`)
    .join(" + ");
  return (
    <div className="rounded-row bg-subtle p-4">
      <div className="flex items-center gap-3">
        <span className="flex size-[38px] shrink-0 items-center justify-center rounded-chip bg-accent text-accent-foreground">
          <PiggyBank className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-foreground">
            Можно сэкономить до {formatMoneyRounded(savings.total_cents)}
          </p>
          <p className="mt-[2px] text-[13px] leading-[1.4] text-dim [overflow-wrap:anywhere]">
            Ваши траты на необязательное: {breakdown}
          </p>
        </div>
      </div>
    </div>
  );
}

function TipsList({
  tips,
  savings,
  onRegenerate,
  isRegenerating,
}: {
  tips: SavingTip[];
  savings?: PotentialSavings | null;
  onRegenerate: () => void;
  isRegenerating: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      {savings && savings.total_cents > 0 ? (
        <PotentialSavingsBlock savings={savings} />
      ) : null}
      <ul className="flex flex-col gap-1">
        {tips.map((tip, index) => (
          // Tips have no id of their own — the LLM output is ephemeral and never
          // persisted, so the position in a freshly generated list is stable enough.
          <TipRow key={index} tip={tip} />
        ))}
      </ul>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-auto w-fit px-3 py-2 text-[13px] font-semibold text-dim hover:bg-transparent hover:text-accent-foreground"
        onClick={onRegenerate}
        disabled={isRegenerating}
      >
        {isRegenerating ? (
          <Loader2 className="animate-spin" aria-hidden />
        ) : (
          <RotateCw aria-hidden />
        )}
        Обновить советы
      </Button>
    </div>
  );
}

export interface SavingTipsCardProps {
  /** Same period/group filter the rest of the dashboard is currently showing. */
  params: DashboardParams;
  className?: string;
}

/**
 * AI-сгенерированные советы по экономии — на тех же расходах, что и остальная
 * сводка, для того же периода/группы. Ничего не запрашивается само по себе:
 * генерация всегда по клику, так что появление карточки не стоит лишнего
 * обращения к модели.
 */
export function SavingTipsCard({ params, className }: SavingTipsCardProps) {
  const mutation = useGenerateSavingTips(params);

  return (
    <SectionCard
      className={className}
      title="Советы по экономии"
      description="Персональные рекомендации на основе ваших расходов"
      descriptionClassName="text-dim"
    >
      {mutation.isPending ? (
        <LoadingState />
      ) : mutation.isError ? (
        <ErrorState error={mutation.error} onRetry={() => mutation.mutate()} />
      ) : mutation.data ? (
        <TipsList
          tips={mutation.data.tips}
          savings={mutation.data.potential_savings}
          onRegenerate={() => mutation.mutate()}
          isRegenerating={mutation.isPending}
        />
      ) : (
        <InitialState onGenerate={() => mutation.mutate()} />
      )}
    </SectionCard>
  );
}
