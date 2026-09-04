import { Banknote, Check } from "lucide-react";
import { toast } from "sonner";

import { UserAvatar } from "@/components/common/UserAvatar";
import { useAuth } from "@/hooks/useAuth";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Member } from "@/types/api";

export interface ParticipantSelectorProps {
  members: Member[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  payerId: string;
  /** Подпись группы чипов для скринридера: сама подпись стоит снаружи. */
  label?: string;
  className?: string;
}

/** Ярлыки «Все» и «Только я» — такие же капсулы, как и участники, но без аватара. */
const SHORTCUT =
  "inline-flex h-11 shrink-0 items-center rounded-full bg-subtle px-4 text-[15px] font-medium text-dim transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";

export function ParticipantSelector({
  members,
  selectedIds,
  onChange,
  payerId,
  label = "Между кем делим",
  className,
}: ParticipantSelectorProps) {
  const { user } = useAuth();
  const selected = new Set(selectedIds);
  const memberIds = members.map((member) => member.user.id);
  const payerName = members.find((member) => member.user.id === payerId)?.user.name;
  const isMember = Boolean(user && memberIds.includes(user.id));

  /** Selection order follows the member list, so the split rows never reshuffle. */
  const commit = (ids: Set<string>) => {
    ids.add(payerId);
    onChange(memberIds.filter((id) => ids.has(id)));
  };

  const toggle = (userId: string) => {
    if (userId === payerId && selected.has(userId)) {
      toast.info(
        `${payerName ?? "Этот участник"} — плательщик, поэтому остаётся в делении. Чтобы убрать, смените «Кто заплатил».`,
      );
      return;
    }
    const next = new Set(selected);
    if (next.has(userId)) next.delete(userId);
    else next.add(userId);
    commit(next);
  };

  const everyoneSelected = memberIds.every((id) => selected.has(id));

  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      {/*
        Чипы — россыпь кнопок, а видимый лейбл стоит вне компонента и ни к чему
        не привязан: без явной группы скринридер прочитает их как безымянные.
      */}
      <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
        {members.map((member) => {
          const id = member.user.id;
          const isSelected = selected.has(id);
          const isPayer = id === payerId;
          const chipLabel = user && id === user.id ? "Вы" : member.user.name;
          return (
            <button
              key={member.id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => toggle(id)}
              className={cn(
                "inline-flex h-11 max-w-full items-center gap-2 rounded-full pl-1.5 pr-4 text-[15px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isSelected
                  ? "bg-accent font-semibold text-accent-foreground hover:bg-accent-hover"
                  : "bg-subtle font-medium text-dim hover:bg-muted hover:text-foreground",
              )}
            >
              <UserAvatar
                user={member.user}
                size="sm"
                className="size-8 text-[13px]"
                fallbackClassName={isSelected ? "bg-card text-accent-foreground" : undefined}
              />
              <span className="max-w-[8rem] truncate">{chipLabel}</span>
              {isPayer ? (
                <Banknote className="size-3.5 shrink-0 opacity-75" aria-hidden="true" />
              ) : isSelected ? (
                <Check className="size-3.5 shrink-0 opacity-75" aria-hidden="true" />
              ) : null}
            </button>
          );
        })}

        <button
          type="button"
          className={SHORTCUT}
          onClick={() => commit(new Set(memberIds))}
          disabled={everyoneSelected}
        >
          Все
        </button>
        {isMember && user ? (
          <button
            type="button"
            className={SHORTCUT}
            onClick={() => commit(new Set([user.id]))}
          >
            Только я
          </button>
        ) : null}
      </div>

      <p className="text-[13px] text-dim">
        В делении {plural(selectedIds.length, "человек", "человека", "человек")}
        {payerName ? ` · плательщик ${payerName} всегда участвует` : ""}
      </p>
    </div>
  );
}
