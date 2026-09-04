import type { ReactNode } from "react";
import { CheckCircle2, Clock, ShieldAlert, Users, Wallet, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState } from "@/components/common/ErrorState";
import { GroupAvatar } from "@/components/common/GroupAvatar";
import { LoadingState } from "@/components/common/LoadingState";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Wordmark } from "@/components/layout/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useAcceptInvite, useInvitePreview } from "@/hooks/useInvites";
import { ApiError, errorMessage } from "@/lib/api";
import { formatDate, plural } from "@/lib/format";
import type { InvitePreview } from "@/types/api";

/**
 * This is the only screen a signed-out visitor can reach that is not the auth
 * pages, so it carries its own shell instead of relying on AppLayout.
 */
function InviteShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-app px-4 py-10">
      <div className="w-full max-w-[520px]">
        <div className="mb-6 flex justify-center">
          <Wordmark />
        </div>
        <div className="rounded-card bg-card p-5 shadow-card sm:p-8">{children}</div>
      </div>
    </div>
  );
}

function StateHeader({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center">
      <span className="mx-auto flex size-12 items-center justify-center rounded-tile bg-accent text-accent-foreground">
        <Icon className="size-[22px]" aria-hidden />
      </span>
      <h1 className="mt-5 text-[22px] font-bold tracking-[-0.02em] [overflow-wrap:anywhere]">
        {title}
      </h1>
      <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}

/** Shown in every state, so accepting is never a blind decision. */
function GroupPreviewCard({ preview }: { preview: InvitePreview }) {
  return (
    <div className="rounded-row bg-subtle p-[18px]">
      <div className="flex items-start gap-3.5">
        <GroupAvatar group={preview.group} size="md" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-semibold tracking-[-0.01em]">
            {preview.group.name}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Badge variant="neutral">
              <Users aria-hidden />
              {plural(preview.group.member_count, "участник", "участника", "участников")}
            </Badge>
            <Badge variant="neutral">
              <Wallet aria-hidden />
              Расчёты в рублях
            </Badge>
          </div>
          {preview.group.description ? (
            <p className="mt-2.5 text-[13px] leading-relaxed text-muted-foreground">
              {preview.group.description}
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2.5 border-t border-border/60 pt-3.5">
        <UserAvatar user={preview.inviter} size="sm" className="shrink-0" />
        <div className="min-w-0 text-[13px]">
          <p className="truncate font-semibold text-foreground">
            Кто пригласил: {preview.inviter.name}
          </p>
          <p className="truncate text-dim">Отправлено на {preview.invited_email}</p>
        </div>
      </div>
    </div>
  );
}

function InvalidLink() {
  return (
    <>
      <StateHeader
        icon={ShieldAlert}
        title="Ссылка-приглашение недействительна"
        description="Ссылка неполная, отозвана или никогда не существовала. Попросите того, кто вас позвал, прислать новую."
      />
      <Button asChild variant="secondary" size="lg" className="mt-6 w-full">
        <Link to="/">Перейти в Складчину</Link>
      </Button>
    </>
  );
}

export default function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  const previewQuery = useInvitePreview(token);
  const acceptInvite = useAcceptInvite();

  const nextQuery = `?next=${encodeURIComponent(`/invite/${token ?? ""}`)}`;

  const handleAccept = () => {
    if (!token) return;
    acceptInvite.mutate(token, {
      onSuccess: (group) => {
        toast.success(`Вы теперь в группе «${group.name}»`);
        navigate(`/groups/${group.id}`, { replace: true });
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  };

  if (!token) {
    return (
      <InviteShell>
        <InvalidLink />
      </InviteShell>
    );
  }

  if (authLoading || previewQuery.isPending) {
    return (
      <InviteShell>
        <LoadingState label="Проверяем приглашение…" />
      </InviteShell>
    );
  }

  if (previewQuery.isError) {
    const status = previewQuery.error instanceof ApiError ? previewQuery.error.status : 0;
    if (status === 404) {
      return (
        <InviteShell>
          <InvalidLink />
        </InviteShell>
      );
    }
    return (
      <InviteShell>
        <ErrorState
          error={previewQuery.error}
          onRetry={() => void previewQuery.refetch()}
        />
        <Button asChild variant="secondary" size="lg" className="mt-6 w-full">
          <Link to="/">Перейти в Складчину</Link>
        </Button>
      </InviteShell>
    );
  }

  const preview = previewQuery.data;
  if (!preview) {
    return (
      <InviteShell>
        <InvalidLink />
      </InviteShell>
    );
  }

  if (preview.already_member) {
    return (
      <InviteShell>
        <StateHeader
          icon={CheckCircle2}
          title="Вы уже в этой группе"
          description={`Принимать нечего — вы уже участник группы «${preview.group.name}».`}
        />
        <div className="mt-6">
          <GroupPreviewCard preview={preview} />
        </div>
        <Button asChild size="lg" className="mt-5 w-full">
          <Link to={`/groups/${preview.group.id}`}>Открыть «{preview.group.name}»</Link>
        </Button>
      </InviteShell>
    );
  }

  if (preview.status === "expired") {
    return (
      <InviteShell>
        <StateHeader
          icon={Clock}
          title="Срок приглашения истёк"
          description={`Ссылка действовала до ${formatDate(preview.expires_at)}. Новую ссылку может создать ${preview.inviter.name}.`}
        />
        <div className="mt-6">
          <GroupPreviewCard preview={preview} />
        </div>
        <Button asChild variant="secondary" size="lg" className="mt-5 w-full">
          <Link to={user ? "/groups" : `/login${nextQuery}`}>
            {user ? "К моим группам" : "Войти в Складчину"}
          </Link>
        </Button>
      </InviteShell>
    );
  }

  if (preview.status === "accepted") {
    return (
      <InviteShell>
        <StateHeader
          icon={XCircle}
          title="Приглашение уже использовано"
          description={`По этой ссылке в группу «${preview.group.name}» уже вступили. Новую ссылку может прислать ${preview.inviter.name}.`}
        />
        <div className="mt-6">
          <GroupPreviewCard preview={preview} />
        </div>
        <Button asChild variant="secondary" size="lg" className="mt-5 w-full">
          <Link to={user ? "/groups" : `/login${nextQuery}`}>
            {user ? "К моим группам" : "Войти в Складчину"}
          </Link>
        </Button>
      </InviteShell>
    );
  }

  if (!user) {
    return (
      <InviteShell>
        <StateHeader
          icon={Users}
          title={`Присоединиться к «${preview.group.name}»`}
          description="Войдите или заведите бесплатный аккаунт, чтобы принять приглашение, — и сразу вернётесь сюда."
        />
        <div className="mt-6">
          <GroupPreviewCard preview={preview} />
        </div>
        <div className="mt-5 grid gap-2.5">
          <Button asChild size="lg" className="w-full">
            <Link to={`/login${nextQuery}`}>Войти</Link>
          </Button>
          <Button asChild variant="secondary" size="lg" className="w-full">
            <Link to={`/register${nextQuery}`}>Создать аккаунт</Link>
          </Button>
        </div>
        <p className="mt-4 text-center text-[13px] text-dim">
          Приглашение действует до {formatDate(preview.expires_at)}.
        </p>
      </InviteShell>
    );
  }

  return (
    <InviteShell>
      <StateHeader
        icon={Users}
        title={`Присоединиться к «${preview.group.name}»`}
        description={`Кто пригласил: ${preview.inviter.name}. Вместе вести общие расходы в этой группе.`}
      />
      <div className="mt-6">
        <GroupPreviewCard preview={preview} />
      </div>
      <Button
        size="lg"
        className="mt-5 w-full"
        onClick={handleAccept}
        disabled={acceptInvite.isPending}
      >
        {acceptInvite.isPending ? "Принимаем…" : "Принять приглашение"}
      </Button>
      <p className="mt-3.5 text-center text-[13px] text-dim">
        Вы вошли как {user.name}. Приглашение действует до {formatDate(preview.expires_at)}.
      </p>
      <div className="mt-1 text-center">
        <Button asChild variant="link" size="sm">
          <Link to="/">Не сейчас — перейти в Складчину</Link>
        </Button>
      </div>
    </InviteShell>
  );
}
