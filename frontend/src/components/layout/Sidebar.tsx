import { Mic, Plus } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAddExpense } from "@/components/layout/AddExpenseContext";
import { NAV_ITEMS } from "@/components/layout/NavItems";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { UserMenu } from "@/components/layout/UserMenu";
import { useVoiceExpenseDialog } from "@/components/layout/VoiceExpenseDialogContext";
import { Wordmark } from "@/components/layout/Wordmark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroups } from "@/hooks/useGroups";
import { plural } from "@/lib/format";
import { formatMoneyRounded } from "@/lib/money";
import { cn } from "@/lib/utils";

const MAX_LISTED_GROUPS = 6;

/** Баланс в сайдбаре — беглый взгляд, поэтому без копеек и своим цветом. */
function balanceTone(cents: number): string {
  if (cents > 0) return "text-positive";
  if (cents < 0) return "text-negative";
  return "text-dim";
}

function GroupLinks() {
  const { data: groups, isPending, isError } = useGroups();

  if (isPending) {
    return (
      <div className="flex flex-col gap-2 px-[18px] py-1">
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-5 w-full rounded-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <p className="px-[18px] py-1 text-[13px] text-dim">Не удалось загрузить группы.</p>
    );
  }

  if (groups.length === 0) {
    return (
      <p className="px-[18px] py-1 text-[13px] text-dim">
        Групп пока нет — создайте первую, чтобы делить расходы.
      </p>
    );
  }

  const listed = groups.slice(0, MAX_LISTED_GROUPS);

  return (
    <ul className="flex flex-col gap-0.5">
      {listed.map((group) => (
        <li key={group.id}>
          <NavLink
            to={`/groups/${group.id}`}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-full px-[18px] py-[9px] transition-colors",
                isActive ? "bg-card shadow-flat" : "hover:bg-white/60",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    "min-w-0 flex-1 truncate text-[15px] text-foreground",
                    isActive && "font-semibold",
                  )}
                >
                  {group.name}
                </span>
                <span
                  className={cn(
                    "shrink-0 text-[13px] font-semibold tabular-nums-money",
                    balanceTone(group.my_net_cents),
                  )}
                >
                  {formatMoneyRounded(group.my_net_cents, { signed: true })}
                </span>
              </>
            )}
          </NavLink>
        </li>
      ))}
      {groups.length > listed.length ? (
        <li>
          <NavLink
            to="/groups"
            className="block rounded-full px-[18px] py-[9px] text-[13px] font-semibold text-accent-foreground transition-colors hover:bg-white/60"
          >
            Ещё {plural(groups.length - listed.length, "группа", "группы", "групп")}
          </NavLink>
        </li>
      ) : null}
    </ul>
  );
}

export function Sidebar() {
  const { openAddExpense } = useAddExpense();
  const { openVoiceExpense } = useVoiceExpenseDialog();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[272px] flex-col gap-7 overflow-y-auto bg-app px-5 py-7 lg:flex">
      <div className="px-2">
        <Wordmark />
      </div>

      <div className="flex items-center gap-1.5">
        {/*
          The row is exactly as wide as the sidebar (272px minus its padding),
          which is too narrow for the full-padding button and an icon button
          side by side — min-w-0 lets it shrink instead of forcing the row
          wider, and the label truncates as the last resort so it never does.
        */}
        <Button
          size="lg"
          className="min-w-0 flex-1 gap-2.5 px-2 font-bold [&_svg]:size-[19px]"
          onClick={() => openAddExpense()}
        >
          <Plus aria-hidden />
          <span className="truncate">Добавить расход</span>
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="size-10 shrink-0"
          aria-label="Добавить расход голосом"
          title="Добавить расход голосом"
          onClick={() => openVoiceExpense()}
        >
          <Mic aria-hidden />
        </Button>
      </div>

      <nav aria-label="Основная навигация" className="flex flex-col gap-1.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3.5 rounded-full px-[18px] py-[13px] text-base transition-colors",
                isActive
                  ? "bg-card font-semibold text-foreground shadow-nav"
                  : "font-medium text-muted-foreground hover:bg-white/60 hover:text-foreground",
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn("size-5 shrink-0", isActive && "text-primary")}
                  aria-hidden
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between gap-2 px-[18px]">
          <h2 className="text-xs font-bold uppercase tracking-[0.09em] text-dim">
            Ваши группы
          </h2>
          <NavLink
            to="/groups/new"
            aria-label="Создать группу"
            className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-card text-accent-foreground shadow-flat transition-colors hover:bg-accent"
          >
            <Plus className="size-3.5" aria-hidden />
          </NavLink>
        </div>
        <GroupLinks />
      </div>

      <div className="mt-auto flex items-center gap-1.5 pt-2">
        <UserMenu variant="full" className="min-w-0 flex-1" />
        <NotificationBell className="shrink-0 bg-card shadow-flat hover:shadow-nav" />
      </div>
    </aside>
  );
}
