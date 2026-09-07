import {
  CalendarDays,
  Coins,
  Mic,
  Plus,
  ReceiptText,
  Settings,
  UserPlus,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, plural } from "@/lib/format";
import type { Group } from "@/types/api";

export interface GroupSummaryHeaderProps {
  group: Group;
  /** Открывает диалог «Новый расход». Без него кнопка действия не рисуется. */
  onAddExpense?: () => void;
  /** Открывает диалог голосового ввода. Без него кнопка действия не рисуется. */
  onVoiceExpense?: () => void;
  /** Открывает диалог загрузки чека. Без него кнопка действия не рисуется. */
  onReceiptExpense?: () => void;
}

/** Мета-чип шапки: иконка и короткий факт о группе. */
function MetaChip({ children }: { children: ReactNode }) {
  return (
    <Badge variant="neutral" className="gap-[7px] px-[15px] py-2 font-medium">
      {children}
    </Badge>
  );
}

export function GroupSummaryHeader({
  group,
  onAddExpense,
  onVoiceExpense,
  onReceiptExpense,
}: GroupSummaryHeaderProps) {
  const isOwner = group.my_role === "owner";
  const description = group.description?.trim();

  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between lg:gap-8">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-[28px] font-bold leading-[1.15] tracking-[-0.025em] text-foreground [overflow-wrap:anywhere] lg:text-[34px] lg:leading-10">
            {group.name}
          </h1>
          {isOwner ? <Badge>Владелец</Badge> : null}
        </div>

        {description ? (
          <p className="mt-2 max-w-[60ch] text-base text-muted-foreground [overflow-wrap:anywhere]">
            {description}
          </p>
        ) : null}

        <div className="mt-3.5 flex flex-wrap items-center gap-2">
          <MetaChip>
            <Users aria-hidden="true" />
            {plural(group.member_count, "участник", "участника", "участников")}
          </MetaChip>
          <MetaChip>
            <Coins aria-hidden="true" />
            Расчёты в рублях
          </MetaChip>
          <MetaChip>
            <CalendarDays aria-hidden="true" />
            Создана {formatDate(group.created_at)}
          </MetaChip>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:max-w-[340px] lg:shrink-0 lg:justify-end">
        {onAddExpense ? (
          <Button className="flex-1 sm:flex-none" onClick={onAddExpense}>
            <Plus />
            Добавить расход
          </Button>
        ) : null}
        {onVoiceExpense || onReceiptExpense ? (
          // Оба AI-входа — одна визуальная группа: при переносе строк они
          // остаются вместе рядом с «Добавить расход», а не разъезжаются.
          <div className="flex shrink-0 gap-1.5">
            {onVoiceExpense ? (
              <Button
                variant="outline"
                size="icon"
                aria-label="Добавить расход голосом"
                title="Добавить расход голосом"
                onClick={onVoiceExpense}
              >
                <Mic />
              </Button>
            ) : null}
            {onReceiptExpense ? (
              <Button
                variant="outline"
                size="icon"
                aria-label="Добавить расход по фото чека"
                title="Добавить расход по фото чека"
                onClick={onReceiptExpense}
              >
                <ReceiptText />
              </Button>
            ) : null}
          </div>
        ) : null}
        <Button variant="outline" className="flex-1 sm:flex-none" asChild>
          <Link to={`/groups/${group.id}/invite`}>
            <UserPlus />
            Пригласить
          </Link>
        </Button>
        {/*
          Кнопка ведёт на одну и ту же страницу для всех: владелец правит группу,
          остальные смотрят состав и уходят из группы. Скрывать её от участника
          значило бы отрезать его от единственного «Выйти из группы».
        */}
        <Button
          variant="outline"
          size="icon"
          aria-label={isOwner ? "Настройки группы" : "Участники группы"}
          asChild
        >
          <Link to={`/groups/${group.id}/settings`}>
            {isOwner ? <Settings /> : <Users />}
          </Link>
        </Button>
      </div>
    </div>
  );
}
