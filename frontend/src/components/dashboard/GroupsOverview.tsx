import { Users } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { dashboardGroupToCard, GroupCard } from "@/components/groups/GroupCard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardGroupSummary } from "@/types/api";

function GroupCardSkeleton() {
  return (
    <Card className="rounded-panel p-5 shadow-panel sm:p-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-[44px] shrink-0 rounded-badge" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <Skeleton className="mt-[22px] h-8 w-40" />
      <Skeleton className="mt-2.5 h-3.5 w-24" />
      <Skeleton className="mt-5 h-3 w-44" />
    </Card>
  );
}

/**
 * Плитки групп на главной — та же {@link GroupCard}, что и на «Группах»:
 * карточка одна на два экрана, чтобы правки не расходились.
 *
 * Полосы «ваша доля» здесь нет намеренно: сводка отдаёт по группе лишь общий
 * расход и баланс, а личной доли в ней нет. Рисовать полосу «на глаз» значило бы
 * показать число, которого никто не считал, — вместо неё внизу карточки стоит
 * честная строка с суммой расходов группы.
 */
export function GroupsOverview({
  groups,
  isLoading,
}: {
  groups?: DashboardGroupSummary[];
  isLoading?: boolean;
}) {
  if (isLoading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <GroupCardSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (!groups || groups.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="Групп пока нет"
        description="Группа — это место, где живут общие расходы. Создайте её и позовите тех, с кем делите счета."
        action={
          <Button asChild>
            <Link to="/groups/new">Создать группу</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {groups.map((group) => (
        <GroupCard
          key={group.group_id}
          className="min-w-0"
          group={dashboardGroupToCard(group)}
          shareCents={group.your_share_cents}
        />
      ))}
    </div>
  );
}
