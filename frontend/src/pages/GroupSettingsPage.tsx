import { Lock, Trash2, UserPlus } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ConfirmButton } from "@/components/common/ConfirmButton";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { GroupForm } from "@/components/groups/GroupForm";
import { MemberList } from "@/components/groups/MemberList";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/hooks/useAuth";
import { useDeleteGroup, useGroup, useMembers } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { formatDate, plural } from "@/lib/format";
import type { Group } from "@/types/api";

/** Настройки — узкая колонка: форма и список участников читаются в одну строку. */
const COLUMN = "flex w-full max-w-[720px] flex-col gap-6";

export default function GroupSettingsPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const currentUser = useCurrentUser();
  const groupQuery = useGroup(groupId);
  const membersQuery = useMembers(groupId);
  const deleteGroup = useDeleteGroup();

  if (!groupId) return <Navigate to="/groups" replace />;

  if (groupQuery.isPending) {
    return (
      <div className={COLUMN}>
        <PageHeader title="Настройки группы" back={{ to: "/groups", label: "Группы" }} />
        <LoadingState label="Загружаем настройки группы…" />
      </div>
    );
  }

  if (groupQuery.isError) {
    return (
      <div className={COLUMN}>
        <PageHeader title="Настройки группы" back={{ to: "/groups", label: "Группы" }} />
        <ErrorState
          error={groupQuery.error}
          onRetry={() => {
            void groupQuery.refetch();
          }}
        />
      </div>
    );
  }

  const group = groupQuery.data;
  const isOwner = group.my_role === "owner";
  const peopleLabel = plural(group.member_count, "человек", "человека", "человек");
  const ownerName =
    membersQuery.data?.find((member) => member.role === "owner")?.user.name ??
    "владелец группы";

  async function handleDelete(target: Group) {
    try {
      await deleteGroup.mutateAsync(target.id);
      toast.success(`Группа «${target.name}» удалена`);
      navigate("/groups");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <div className={COLUMN}>
      <PageHeader
        back={{ to: `/groups/${group.id}`, label: group.name }}
        title="Настройки группы"
        description={
          <>
            Управляйте группой{" "}
            <span className="font-semibold text-foreground">«{group.name}»</span> и её
            участниками.
          </>
        }
      />

      <SectionCard
        title="Данные группы"
        description={
          isOwner
            ? "Измените название или описание. Все расходы в группе — в рублях."
            : "Название и описание группы. Все расходы — в рублях."
        }
      >
        {isOwner ? (
          <GroupForm group={group} />
        ) : (
          <div className="flex flex-col gap-4">
            <Alert variant="info">
              <Lock aria-hidden="true" />
              <AlertTitle>Только просмотр</AlertTitle>
              <AlertDescription>
                Менять эти данные может только {ownerName}. Добавлять расходы,
                рассчитываться и приглашать людей вы по-прежнему можете.
              </AlertDescription>
            </Alert>
            <ReadOnlyDetails group={group} />
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Участники"
        description={`В группе ${peopleLabel}.`}
        action={
          <Button asChild variant="outline" size="sm">
            <Link to={`/groups/${group.id}/invite`}>
              <UserPlus aria-hidden="true" />
              Пригласить
            </Link>
          </Button>
        }
        contentClassName="p-2 pt-0 sm:p-3 sm:pt-0"
      >
        {membersQuery.isPending ? (
          <MemberListSkeleton />
        ) : membersQuery.isError ? (
          <ErrorState
            error={membersQuery.error}
            onRetry={() => {
              void membersQuery.refetch();
            }}
          />
        ) : (
          <MemberList
            group={group}
            members={membersQuery.data}
            currentUserId={currentUser.id}
          />
        )}
      </SectionCard>

      {isOwner ? (
        <section className="rounded-card border border-negative/25 bg-negative-surface p-5 sm:p-7">
          <h2 className="text-[19px] font-bold tracking-[-0.02em] text-negative sm:text-[20px]">
            Опасная зона
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Удаление группы необратимо и касается всех, кто в ней есть.
          </p>
          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[15px] leading-relaxed text-muted-foreground">
              Все расходы, переводы и балансы группы «{group.name}» исчезнут у всех
              участников — сейчас в ней {peopleLabel}. Непогашенные долги при этом не
              закрываются: они просто перестают существовать.
            </p>
            <ConfirmButton
              title={`Удалить группу «${group.name}»?`}
              description={`Группа и вся её история будут удалены у всех участников — это ${peopleLabel}. Вернуть данные будет нельзя.`}
              confirmLabel="Удалить группу"
              destructive
              onConfirm={() => handleDelete(group)}
            >
              <Button
                variant="destructive"
                className="shrink-0"
                disabled={deleteGroup.isPending}
              >
                <Trash2 aria-hidden="true" />
                Удалить группу
              </Button>
            </ConfirmButton>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ReadOnlyDetails({ group }: { group: Group }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-row bg-subtle px-[18px] py-3.5">
        <dt className="text-[13px] text-dim">Название</dt>
        <dd className="mt-1 text-[15px] font-semibold text-foreground">{group.name}</dd>
      </div>
      <div className="rounded-row bg-subtle px-[18px] py-3.5">
        <dt className="text-[13px] text-dim">Создана</dt>
        <dd className="mt-1 text-[15px] font-semibold text-foreground">
          {formatDate(group.created_at)}
        </dd>
      </div>
      <div className="rounded-row bg-subtle px-[18px] py-3.5 sm:col-span-2">
        <dt className="text-[13px] text-dim">Описание</dt>
        <dd className="mt-1 text-[15px] text-foreground">
          {group.description?.trim() || <span className="text-dim">Без описания</span>}
        </dd>
      </div>
    </dl>
  );
}

function MemberListSkeleton() {
  return (
    <div className="flex flex-col gap-1" aria-hidden="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="flex items-center gap-3.5 rounded-row px-3 py-3">
          <Skeleton className="size-[42px] rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-48 max-w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
