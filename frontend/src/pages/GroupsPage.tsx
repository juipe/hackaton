import { Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { GroupCard } from "@/components/groups/GroupCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroups } from "@/hooks/useGroups";

/** Одна сетка на весь экран: карточки, скелетон и пустое место совпадают. */
const GRID = "grid gap-5 sm:grid-cols-2 lg:grid-cols-3";

export default function GroupsPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Группы"
        description="Все общие счета, в которых вы участвуете, и ваш баланс в каждом из них."
        actions={
          <Button asChild>
            <Link to="/groups/new">
              <Plus aria-hidden="true" />
              Новая группа
            </Link>
          </Button>
        }
      />
      <GroupsContent />
    </div>
  );
}

function GroupsContent() {
  const groupsQuery = useGroups();

  if (groupsQuery.isPending) return <GroupGridSkeleton />;

  if (groupsQuery.isError) {
    return (
      <ErrorState
        error={groupsQuery.error}
        onRetry={() => {
          void groupsQuery.refetch();
        }}
      />
    );
  }

  const groups = groupsQuery.data;

  if (groups.length === 0) return <NoGroups />;

  return (
    <div className={GRID}>
      {groups.map((group) => (
        <GroupCard key={group.id} group={group} />
      ))}
    </div>
  );
}

/**
 * Пустой экран — такая же карточка, как заполненные: человек видит ту же
 * форму, в которой скоро появятся группы, а не рамку-заглушку.
 */
function NoGroups() {
  return (
    <div className="rounded-card bg-card p-6 text-center shadow-card sm:p-10">
      <span className="mx-auto flex size-14 items-center justify-center rounded-badge bg-accent text-accent-foreground">
        <Users className="size-6" aria-hidden="true" />
      </span>
      <h2 className="mt-5 text-[19px] font-bold tracking-[-0.02em] text-foreground sm:text-[20px]">
        Групп пока нет
      </h2>
      <p className="mx-auto mt-2 max-w-[52ch] text-[15px] leading-relaxed text-muted-foreground">
        Группа — это общий счёт: добавьте людей, с которыми делите расходы,
        записывайте их по мере появления, а «Складчина» будет считать, кто кому
        должен, пока вы не рассчитаетесь.
      </p>
      <Button asChild className="mt-6">
        <Link to="/groups/new">
          <Plus aria-hidden="true" />
          Создать первую группу
        </Link>
      </Button>
    </div>
  );
}

function GroupGridSkeleton() {
  return (
    <div className={GRID} aria-hidden="true">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-panel bg-card p-5 shadow-panel sm:p-6">
          <div className="flex items-center gap-3">
            <Skeleton className="size-[44px] rounded-badge" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/5" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
          <Skeleton className="mt-[22px] h-8 w-2/5" />
          <Skeleton className="mt-2 h-3.5 w-24" />
          <Skeleton className="mt-5 h-3 w-44" />
        </div>
      ))}
    </div>
  );
}
