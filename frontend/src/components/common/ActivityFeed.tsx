import { History } from "lucide-react";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Money } from "@/components/common/Money";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative, joinNames, pluralWord } from "@/lib/format";
import { DEFAULT_CURRENCY } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Activity } from "@/types/api";

type Meta = Record<string, unknown>;

function text(meta: Meta, key: string): string | null {
  const value = meta?.[key];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function count(meta: Meta, key: string): number | null {
  const value = meta?.[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function flag(meta: Meta, key: string): boolean {
  return meta?.[key] === true;
}

function stringList(meta: Meta, key: string): string[] {
  const value = meta?.[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim() !== "");
}

/** Human-readable Russian names for the group fields the API reports as changed. */
const FIELD_LABELS: Record<string, string> = {
  name: "название",
  description: "описание",
  currency: "валюта",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field.replace(/_/g, " ");
}

/** Bold nouns make the feed scannable without adding a second colour. */
function Subject({ children }: { children: ReactNode }) {
  return <span className="font-semibold text-foreground">{children}</span>;
}

/** Russian quotation marks around a name, with a graceful line for a missing one. */
function Quoted({ name, fallback }: { name: string | null; fallback: string }) {
  if (!name) return <>{fallback}</>;
  return <>«<Subject>{name}</Subject>»</>;
}

/**
 * Money in the feed is a fact, not a balance, so it is never tinted: the positive
 * and negative tones belong exclusively to the sign of what you owe.
 */
function Amount({ meta }: { meta: Meta }) {
  const cents = count(meta, "amount_cents");
  if (cents === null) return null;
  return (
    <>
      {" — "}
      <Money
        cents={cents}
        currency={DEFAULT_CURRENCY}
        tone={false}
        className="font-semibold text-foreground"
      />
    </>
  );
}

interface Sentence {
  node: ReactNode;
  /** True when the sentence already names the group, so the meta line can skip it. */
  mentionsGroup: boolean;
}

/**
 * Russian past-tense verbs agree with the speaker's gender, which the user model
 * does not know. So an event is written impersonally — as a noun phrase — and the
 * person behind it moves to the muted second line rendered below.
 */
function describe(activity: Activity): Sentence {
  const meta: Meta = activity.meta ?? {};
  const actor = activity.actor?.name?.trim() || "Участник";
  const groupName = activity.group_name?.trim() || null;
  const title = text(meta, "title");

  switch (activity.type) {
    case "group_created":
      return {
        node: (
          <>
            Создана группа{" "}
            <Quoted name={text(meta, "name") ?? groupName} fallback="без названия" />
          </>
        ),
        mentionsGroup: true,
      };

    case "group_updated": {
      const changed = stringList(meta, "changed").map(fieldLabel);
      return {
        node: (
          <>
            Изменена группа{" "}
            <Quoted name={text(meta, "name") ?? groupName} fallback="без названия" />
            {changed.length > 0 ? ` — ${joinNames(changed, 3)}` : ""}
          </>
        ),
        mentionsGroup: true,
      };
    }

    case "member_joined":
      return {
        node: (
          <>
            Новый участник:{" "}
            <Subject>{text(meta, "member_name") ?? text(meta, "name") ?? actor}</Subject>
          </>
        ),
        mentionsGroup: false,
      };

    case "member_removed": {
      const who = text(meta, "name") ?? text(meta, "member_name");
      if (flag(meta, "left") || (who && who === activity.actor?.name)) {
        return {
          node: (
            <>
              <Subject>{who ?? actor}</Subject> больше не в группе{" "}
              <Quoted name={groupName} fallback="без названия" />
            </>
          ),
          mentionsGroup: true,
        };
      }
      return {
        node: (
          <>
            Участник{who ? <> <Subject>{who}</Subject></> : null} удалён из группы{" "}
            <Quoted name={groupName} fallback="без названия" />
          </>
        ),
        mentionsGroup: true,
      };
    }

    case "expense_created":
      return {
        node: (
          <>
            Добавлен расход <Quoted name={title} fallback="без названия" />
            <Amount meta={meta} />
          </>
        ),
        mentionsGroup: false,
      };

    case "expense_updated":
      return {
        node: (
          <>
            Изменён расход <Quoted name={title} fallback="без названия" />
            <Amount meta={meta} />
          </>
        ),
        mentionsGroup: false,
      };

    case "expense_deleted":
      return {
        node: (
          <>
            Удалён расход <Quoted name={title} fallback="без названия" />
            <Amount meta={meta} />
          </>
        ),
        mentionsGroup: false,
      };

    case "payment_created": {
      const from = text(meta, "from_name") ?? actor;
      const to = text(meta, "to_name") ?? "участник";
      const cents = count(meta, "amount_cents");
      return {
        node: (
          <>
            Перевод: <Subject>{from}</Subject> → <Subject>{to}</Subject>
            {cents === null ? null : (
              <>
                {", "}
                <Money
                  cents={cents}
                  currency={DEFAULT_CURRENCY}
                  tone={false}
                  className="font-semibold text-foreground"
                />
              </>
            )}
          </>
        ),
        mentionsGroup: false,
      };
    }

    case "invite_created": {
      const email = text(meta, "invited_email");
      return {
        node: (
          <>
            Приглашение отправлено
            {email ? (
              <>
                : <Subject>{email}</Subject>
              </>
            ) : null}
          </>
        ),
        mentionsGroup: false,
      };
    }

    case "debt_simplified": {
      const before = count(meta, "before");
      const after = count(meta, "after");
      if (before === null || after === null) {
        return { node: <>Долги упрощены</>, mentionsGroup: false };
      }
      return {
        node: (
          <>
            Долги упрощены: <Subject>{before}</Subject> → <Subject>{after}</Subject>{" "}
            {pluralWord(after, "перевод", "перевода", "переводов")}
          </>
        ),
        mentionsGroup: false,
      };
    }

    default:
      return {
        node: (
          <>
            Изменения в группе <Quoted name={groupName} fallback="без названия" />
          </>
        ),
        mentionsGroup: true,
      };
  }
}

export interface ActivityFeedProps {
  activities?: Activity[];
  isLoading?: boolean;
  error?: unknown;
  showGroup?: boolean;
  emptyLabel?: string;
  className?: string;
}

export function ActivityFeed({
  activities,
  isLoading,
  error,
  showGroup = false,
  emptyLabel = "Пока ничего не происходило",
  className,
}: ActivityFeedProps) {
  if (isLoading) {
    return (
      <div className={cn("flex flex-col gap-1", className)}>
        {[0, 1, 2, 3].map((row) => (
          <div key={row} className="flex items-start gap-3.5 rounded-tile p-3">
            <Skeleton className="size-[38px] shrink-0 rounded-chip bg-muted" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4 bg-muted" />
              <Skeleton className="h-3 w-24 bg-muted" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) return <ErrorState error={error} className={className} />;

  if (!activities || activities.length === 0) {
    return (
      <EmptyState
        icon={History}
        title={emptyLabel}
        description="Здесь появятся расходы, переводы и новые участники."
        className={className}
      />
    );
  }

  return (
    <ol className={cn("flex flex-col gap-1", className)}>
      {activities.map((activity) => {
        const { node, mentionsGroup } = describe(activity);
        const showGroupChip = showGroup && !mentionsGroup && Boolean(activity.group_name);
        const actorName = activity.actor?.name?.trim() || "Участник";
        return (
          <li
            key={activity.id}
            className="flex items-start gap-3.5 rounded-tile p-3 transition-colors hover:bg-subtle"
          >
            {/* Скруглённый квадрат, а не круг: в ленте аватар — метка автора
                рядом с текстом, и круг спорил бы с круглыми аватарами людей
                в списках долгов, где кружок значит «участник». */}
            <UserAvatar
              user={activity.actor}
              size="md"
              className="rounded-chip [&>span]:rounded-chip"
            />
            <div className="min-w-0 flex-1">
              <p className="text-[15px] leading-[1.4] text-foreground [overflow-wrap:anywhere]">
                {node}
              </p>
              <p className="mt-[3px] text-[13px] leading-[1.4] text-dim [overflow-wrap:anywhere]">
                {actorName} · {formatRelative(activity.created_at)}
                {showGroupChip ? ` · ${activity.group_name}` : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
