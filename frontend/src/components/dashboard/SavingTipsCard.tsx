import { Lightbulb, Loader2, RotateCw, Sparkles } from "lucide-react";

import { ErrorState } from "@/components/common/ErrorState";
import { SectionCard } from "@/components/common/SectionCard";
import { Button } from "@/components/ui/button";
import { useGenerateSavingTips } from "@/hooks/useDashboard";
import type { DashboardParams, SavingTip } from "@/types/api";

function InitialState({ onGenerate }: { onGenerate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-row bg-subtle px-5 py-9 text-center sm:px-6 sm:py-10">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-accent-foreground">
        <Sparkles className="size-6" aria-hidden />
      </span>
      <p className="mx-auto max-w-[42ch] text-[15px] leading-relaxed text-muted-foreground">
        Qwen разберёт расходы за выбранный период и предложит пару советов, как сократить
        траты.
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
        Qwen работает локально — это может занять немного времени.
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

function TipsList({
  tips,
  onRegenerate,
  isRegenerating,
}: {
  tips: SavingTip[];
  onRegenerate: () => void;
  isRegenerating: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
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
 * обращения к Qwen.
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
          onRegenerate={() => mutation.mutate()}
          isRegenerating={mutation.isPending}
        />
      ) : (
        <InitialState onGenerate={() => mutation.mutate()} />
      )}
    </SectionCard>
  );
}
