import { LogOut, UserMinus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { ConfirmButton } from "@/components/common/ConfirmButton";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useRemoveMember } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Group, Member } from "@/types/api";

export interface MemberListProps {
  group: Group;
  members: Member[];
  currentUserId: string;
}

export function MemberList({ group, members, currentUserId }: MemberListProps) {
  const navigate = useNavigate();
  const removeMember = useRemoveMember(group.id);
  const [refusal, setRefusal] = useState<{ userId: string; message: string } | null>(null);

  const viewerIsOwner = group.my_role === "owner";

  async function handleRemove(member: Member, leaving: boolean) {
    setRefusal(null);
    try {
      await removeMember.mutateAsync(member.user.id);
      if (leaving) {
        toast.success(`Вы вышли из группы «${group.name}»`);
        navigate("/groups");
        return;
      }
      toast.success(`Участник ${member.user.name} удалён из группы «${group.name}»`);
    } catch (error) {
      // The server's wording is the instruction the user needs — it explains which
      // debt is in the way — so it is kept verbatim and pinned to the row it belongs
      // to, not just flashed in a toast.
      const message = errorMessage(error);
      setRefusal({ userId: member.user.id, message });
      toast.error(message);
    }
  }

  if (members.length === 0) {
    return (
      <p className="px-3 py-2 text-[15px] text-muted-foreground">
        Участников пока нет. Пригласите кого-нибудь, чтобы делить расходы вместе.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-0.5">
      {members.map((member) => {
        const isSelf = member.user.id === currentUserId;
        const isOwnerRow = member.role === "owner";
        const canRemove = viewerIsOwner && !isSelf && !isOwnerRow;
        const canLeave = isSelf && !isOwnerRow;

        return (
          <li key={member.id}>
            <div className="flex items-center gap-3.5 rounded-row px-3 py-3 transition-colors hover:bg-subtle sm:px-4">
              <UserAvatar user={member.user} size="lg" className="shrink-0" />

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="truncate text-base font-semibold text-foreground">
                    {member.user.name}
                  </span>
                  <Badge variant={isOwnerRow ? "default" : "neutral"}>
                    {isOwnerRow ? "Владелец" : "Участник"}
                  </Badge>
                  {isSelf ? <Badge variant="neutral">Вы</Badge> : null}
                </div>
                <p className="mt-0.5 break-words text-[13px] text-dim sm:truncate">
                  {member.user.email} · в группе с {formatDate(member.joined_at)}
                </p>
              </div>

              {canRemove ? (
                <ConfirmButton
                  title="Удалить участника из группы?"
                  description={`Участник: ${member.user.name}. Доступ к группе «${group.name}» будет закрыт. Расходы, которые уже оплачены, останутся в истории группы.`}
                  confirmLabel="Удалить участника"
                  destructive
                  onConfirm={() => handleRemove(member, false)}
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-11 shrink-0 hover:bg-negative-surface hover:text-negative"
                    disabled={removeMember.isPending}
                    aria-label={`Удалить участника из группы: ${member.user.name}`}
                  >
                    <UserMinus aria-hidden="true" />
                    <span className="hidden sm:inline">Удалить</span>
                  </Button>
                </ConfirmButton>
              ) : canLeave ? (
                <ConfirmButton
                  title={`Выйти из группы «${group.name}»?`}
                  description="Вы перестанете видеть расходы этой группы. Вас можно будет пригласить снова, а прошлые расходы останутся в группе."
                  confirmLabel="Выйти из группы"
                  destructive
                  onConfirm={() => handleRemove(member, true)}
                >
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-11 shrink-0"
                    disabled={removeMember.isPending}
                    aria-label={`Выйти из группы «${group.name}»`}
                  >
                    <LogOut aria-hidden="true" />
                    <span className="hidden sm:inline">Выйти</span>
                  </Button>
                </ConfirmButton>
              ) : isSelf && isOwnerRow ? (
                <span className="hidden max-w-[11rem] shrink-0 text-right text-[13px] leading-snug text-dim lg:block">
                  Владелец остаётся в группе — её можно только удалить
                </span>
              ) : null}
            </div>

            {refusal?.userId === member.user.id ? (
              <Alert variant="destructive" className="mx-3 mb-2 mt-1 w-auto sm:mx-4">
                <AlertDescription>{refusal.message}</AlertDescription>
              </Alert>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
