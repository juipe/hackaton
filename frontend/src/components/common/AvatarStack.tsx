import { UserAvatar, type UserAvatarSize } from "@/components/common/UserAvatar";
import { cn } from "@/lib/utils";
import { joinNames } from "@/lib/format";

/** Размер кружка «+N» повторяет размеры `UserAvatar`. */
const SIZES: Record<UserAvatarSize, { root: string; text: string }> = {
  sm: { root: "size-[34px]", text: "text-[13px]" },
  md: { root: "size-[38px]", text: "text-[14px]" },
  lg: { root: "size-[42px]", text: "text-[15px]" },
  xl: { root: "size-[46px]", text: "text-[15px]" },
};

export interface AvatarStackProps {
  users: { id: string; name: string }[];
  size?: UserAvatarSize;
  /** Сколько аватаров показать до кружка «+N». */
  max?: number;
  /**
   * Кольцо вокруг каждого аватара — оно должно совпадать с фоном, на котором
   * стоит стопка, иначе нахлёст выглядит грязно. По умолчанию — цвет карточки.
   */
  ringClassName?: string;
  className?: string;
}

export function AvatarStack({
  users,
  size = "md",
  max = 3,
  ringClassName = "shadow-[0_0_0_3px_hsl(var(--card))]",
  className,
}: AvatarStackProps) {
  if (users.length === 0) return null;

  const scale = SIZES[size] ?? SIZES.md;
  const shown = users.slice(0, Math.max(1, max));
  const hidden = users.length - shown.length;

  return (
    <div
      className={cn("flex shrink-0 items-center", className)}
      role="img"
      aria-label={joinNames(
        users.map((user) => user.name),
        users.length,
      )}
    >
      {shown.map((user, index) => (
        <UserAvatar
          key={user.id}
          user={user}
          size={size}
          className={cn(index > 0 && "-ml-3", ringClassName)}
        />
      ))}
      {hidden > 0 ? (
        <span
          aria-hidden
          className={cn(
            "-ml-3 flex shrink-0 items-center justify-center rounded-full bg-muted font-bold text-muted-foreground",
            scale.root,
            scale.text,
            ringClassName,
          )}
        >
          +{hidden}
        </span>
      ) : null}
    </div>
  );
}
