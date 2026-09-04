import { useState, type FormEvent } from "react";
import { ArrowLeft, Clock, Link2, MailPlus, ShieldAlert, Trash2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ConfirmButton } from "@/components/common/ConfirmButton";
import { CopyButton } from "@/components/common/CopyButton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGroup } from "@/hooks/useGroups";
import { useCreateInvite, useGroupInvites, useRevokeInvite } from "@/hooks/useInvites";
import { errorMessage } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/format";
import type { Invite, InviteCreated, InviteStatus } from "@/types/api";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const STATUS_META: Record<
  InviteStatus,
  { label: string; variant: "default" | "success" | "muted" }
> = {
  pending: { label: "Ожидает", variant: "default" },
  accepted: { label: "Принято", variant: "success" },
  expired: { label: "Истекло", variant: "muted" },
};

function inviteDetail(invite: Invite): string {
  if (invite.status === "accepted") {
    return invite.accepted_at
      ? `Принято ${formatDate(invite.accepted_at)}`
      : "Ссылка уже использована";
  }
  if (invite.status === "expired") return `Истекло ${formatDate(invite.expires_at)}`;
  return `Действует до ${formatDate(invite.expires_at)}`;
}

function InviteRow({
  invite,
  onRevoke,
}: {
  invite: Invite;
  onRevoke: (invite: Invite) => Promise<void>;
}) {
  const meta = STATUS_META[invite.status];
  return (
    <li className="flex items-start gap-3.5 rounded-row px-[18px] py-3.5 transition-colors hover:bg-subtle">
      <UserAvatar user={invite.inviter} size="md" className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[15px] font-semibold">{invite.invited_email}</p>
        <p className="mt-0.5 truncate text-[13px] text-dim">
          Кто пригласил: {invite.inviter.name} · {formatRelative(invite.created_at)}
        </p>
        <p className="truncate text-[13px] text-dim">{inviteDetail(invite)}</p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Badge variant={meta.variant}>{meta.label}</Badge>
        {invite.status === "accepted" ? null : (
          <ConfirmButton
            title="Отозвать приглашение?"
            description={`Ссылка для ${invite.invited_email} перестанет работать сразу же. Новую можно создать в любой момент.`}
            confirmLabel="Отозвать"
            destructive
            onConfirm={() => onRevoke(invite)}
          >
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Отозвать приглашение для ${invite.invited_email}`}
            >
              <Trash2 />
            </Button>
          </ConfirmButton>
        )}
      </div>
    </li>
  );
}

export default function GroupInvitePage() {
  const { groupId } = useParams<{ groupId: string }>();
  const id = groupId ?? "";

  const groupQuery = useGroup(id);
  const invitesQuery = useGroupInvites(id);
  const createInvite = useCreateInvite(id);
  const revokeInvite = useRevokeInvite(id);

  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [created, setCreated] = useState<InviteCreated | null>(null);

  const group = groupQuery.data;
  const invites = invitesQuery.data ?? [];

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = email.trim().toLowerCase();
    if (!EMAIL_PATTERN.test(value)) {
      setFieldError("Введите корректный адрес, например masha@example.ru");
      return;
    }
    setFieldError(null);
    createInvite.mutate(value, {
      onSuccess: (invite) => {
        setCreated(invite);
        setEmail("");
        toast.success("Ссылка-приглашение готова");
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  };

  const handleRevoke = async (invite: Invite) => {
    try {
      await revokeInvite.mutateAsync(invite.id);
      if (created?.id === invite.id) setCreated(null);
      toast.success(`Приглашение для ${invite.invited_email} отозвано`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  if (groupQuery.isError) {
    return (
      <div className="py-10">
        <div className="mx-auto w-full max-w-[520px] rounded-card bg-card p-5 shadow-card sm:p-8">
          <ErrorState error={groupQuery.error} onRetry={() => void groupQuery.refetch()} />
          <p className="mt-4 text-center text-[15px] text-muted-foreground">
            Приглашать в группу могут только её участники.
          </p>
          <div className="mt-5 flex justify-center">
            <Button asChild variant="secondary">
              <Link to="/groups">
                <ArrowLeft aria-hidden />
                К группам
              </Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Пригласить в группу"
        description={
          group
            ? `Создайте ссылку, по которой человек войдёт в группу «${group.name}».`
            : "Создайте ссылку, по которой человек войдёт в эту группу."
        }
        back={{ to: `/groups/${id}`, label: group?.name ?? "Группа" }}
      />

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <SectionCard
          title="Новое приглашение"
          description="Почта — это подпись приглашения. Впустит человека в группу сама ссылка."
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-email">Адрес электронной почты</Label>
              <Input
                id="invite-email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="masha@example.ru"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (fieldError) setFieldError(null);
                }}
                aria-invalid={fieldError ? true : undefined}
                aria-describedby={fieldError ? "invite-email-error" : "invite-email-hint"}
              />
              {fieldError ? (
                <p id="invite-email-error" className="text-[13px] text-destructive">
                  {fieldError}
                </p>
              ) : (
                <p id="invite-email-hint" className="text-[13px] leading-relaxed text-dim">
                  Он не обязан совпадать с почтой аккаунта, который человек в итоге заведёт.
                </p>
              )}
            </div>
            <Button
              type="submit"
              size="lg"
              className="w-full sm:w-auto sm:self-start"
              disabled={createInvite.isPending || !groupId}
            >
              <MailPlus aria-hidden />
              {createInvite.isPending ? "Создаём…" : "Создать приглашение"}
            </Button>
          </form>

          <Alert variant="info" className="mt-5">
            <ShieldAlert />
            <AlertTitle>Ссылка и есть приглашение</AlertTitle>
            <AlertDescription>
              Почтового сервиса в этой сборке нет, письма никому не уходят. Скопируйте
              ссылку ниже и передайте её сами. Войти в группу сможет любой, кто её
              откроет, — отправляйте только тому, кого действительно приглашаете.
            </AlertDescription>
          </Alert>

          {created ? (
            <div className="mt-5 rounded-row bg-subtle p-[18px]">
              <p className="flex items-center gap-2 text-[15px] font-semibold">
                <Link2 className="size-[17px] shrink-0" aria-hidden />
                <span className="min-w-0 truncate">Ссылка для {created.invited_email}</span>
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Input
                  readOnly
                  value={created.invite_url}
                  aria-label="Ссылка-приглашение"
                  onFocus={(event) => event.currentTarget.select()}
                  className="min-w-0 bg-card font-mono text-[13px]"
                />
                <CopyButton
                  value={created.invite_url}
                  label="Копировать ссылку"
                  className="shrink-0"
                />
              </div>
              <p className="mt-2.5 flex items-start gap-1.5 text-[13px] leading-relaxed text-dim">
                <Clock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                <span>
                  Действует до {formatDate(created.expires_at)}. После этого ссылка
                  перестанет работать и понадобится новая.
                </span>
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-[18px] mt-2"
                onClick={() => setCreated(null)}
              >
                Пригласить кого-то ещё
              </Button>
            </div>
          ) : null}
        </SectionCard>

        {/*
          Строки приглашений держат собственный px-[18px], поэтому карточка
          отдаёт им свои боковые отступы — иначе текст строки уехал бы
          относительно заголовка секции.
        */}
        <SectionCard
          title="Приглашения"
          description="Все ссылки, созданные для этой группы, и что с ними стало."
          contentClassName="px-[2px] pb-3 pt-0 sm:px-[10px] sm:pb-4"
        >
          {invitesQuery.isPending ? (
            <LoadingState label="Загружаем приглашения…" />
          ) : invitesQuery.isError ? (
            <div className="px-3 pb-1">
              <ErrorState
                error={invitesQuery.error}
                onRetry={() => void invitesQuery.refetch()}
              />
            </div>
          ) : invites.length === 0 ? (
            <div className="px-3 pb-1">
              <EmptyState
                icon={MailPlus}
                title="Приглашений пока нет"
                description="Создайте ссылку и отправьте её тому, кого хотите добавить."
              />
            </div>
          ) : (
            <ul className="flex flex-col gap-1">
              {invites.map((invite) => (
                <InviteRow key={invite.id} invite={invite} onRevoke={handleRevoke} />
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
