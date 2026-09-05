import { Bell, BellRing } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Money } from "@/components/common/Money";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarkNotificationsRead, useNotifications } from "@/hooks/useNotifications";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Notification } from "@/types/api";

const MAX_VISIBLE = 10;

function NotificationsLoading() {
  return (
    <div className="flex flex-col gap-1 p-2" data-testid="notifications-loading">
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-start gap-3 rounded-tile p-2.5">
          <Skeleton className="size-[34px] shrink-0 rounded-chip bg-muted" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4 bg-muted" />
            <Skeleton className="h-3 w-1/3 bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

function NotificationRow({ notification }: { notification: Notification }) {
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-tile p-2.5 transition-colors",
        !notification.is_read && "bg-subtle",
      )}
    >
      <span className="flex size-[34px] shrink-0 items-center justify-center rounded-chip bg-accent text-accent-foreground">
        <BellRing className="size-[16px]" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] leading-[1.4] text-foreground [overflow-wrap:anywhere]">
          {notification.message}
        </p>
        <p className="mt-[3px] flex items-center gap-1.5 text-[12px] leading-[1.4] text-dim">
          <Money
            cents={notification.amount_due_cents}
            currency={notification.currency}
            tone={false}
            className="font-semibold text-foreground"
          />
          <span aria-hidden>·</span>
          {formatRelative(notification.created_at)}
        </p>
      </div>
    </li>
  );
}

/**
 * Debt-reminder bell, next to the profile menu — see `TopBar` (mobile) and
 * `Sidebar` (desktop). Opening the panel marks the visible reminders read.
 */
export function NotificationBell({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const { data: notifications, isPending, isError, error, refetch } = useNotifications();
  const markRead = useMarkNotificationsRead();

  const hasUnread = Boolean(notifications?.some((notification) => !notification.is_read));

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next && hasUnread) {
      markRead.mutate();
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Уведомления"
          className={cn(
            "relative flex size-10 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            className,
          )}
        >
          <Bell className="size-5" aria-hidden />
          {hasUnread ? (
            <span
              data-testid="notification-unread-dot"
              aria-hidden
              className="absolute right-2 top-2 size-2.5 rounded-full bg-primary ring-2 ring-app"
            />
          ) : null}
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-2">
        <div className="flex items-center justify-between px-2 py-1.5">
          <h2 className="text-[13px] font-bold uppercase tracking-[0.09em] text-dim">
            Уведомления
          </h2>
        </div>

        {isPending ? (
          <NotificationsLoading />
        ) : isError ? (
          <ErrorState
            error={error}
            onRetry={() => void refetch()}
            className="rounded-tile px-3 py-6"
          />
        ) : !notifications || notifications.length === 0 ? (
          <EmptyState
            icon={Bell}
            title="Пока нет уведомлений"
            description="Здесь появятся напоминания о новых расходах, в которых вы участвуете."
            className="rounded-tile px-3 py-6"
          />
        ) : (
          <ol className="flex max-h-[70vh] flex-col gap-1 overflow-y-auto">
            {/* The API already caps this at 10, newest first — sliced again here
                so the panel never shows more even if that ever changes. */}
            {notifications.slice(0, MAX_VISIBLE).map((notification) => (
              <NotificationRow key={notification.id} notification={notification} />
            ))}
          </ol>
        )}
      </PopoverContent>
    </Popover>
  );
}
