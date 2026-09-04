import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { avatarTone, cn, initials } from "@/lib/utils";

/**
 * Размеры из макета: 34 / 38 / 42 / 46. Числа некруглые, потому что аватар
 * всегда стоит рядом с текстом строки и подгонялся под его высоту, а не под
 * шкалу отступов.
 */
const SIZES = {
  sm: { root: "size-[34px]", text: "text-[13px]" },
  md: { root: "size-[38px]", text: "text-[14px]" },
  lg: { root: "size-[42px]", text: "text-[15px]" },
  xl: { root: "size-[46px]", text: "text-[15px]" },
} as const;

export type UserAvatarSize = keyof typeof SIZES;

export interface UserAvatarProps {
  user: { id: string; name: string };
  size?: UserAvatarSize;
  className?: string;
  /**
   * Перебивает цветовую пару аватара. Нужно там, где аватар стоит на цветной
   * плашке того же оттенка (выбранный чип участника, своя строка балансов):
   * зелёный кружок на зелёном фоне превращается в висящую букву, поэтому
   * макет делает его белым.
   */
  fallbackClassName?: string;
}

export function UserAvatar({
  user,
  size = "md",
  className,
  fallbackClassName,
}: UserAvatarProps) {
  const scale = SIZES[size] ?? SIZES.md;
  return (
    <Avatar className={cn(scale.root, className)}>
      <AvatarFallback
        aria-hidden
        className={cn("font-bold", scale.text, avatarTone(user.id), fallbackClassName)}
      >
        {initials(user.name) || "?"}
      </AvatarFallback>
      <span className="sr-only">{user.name}</span>
    </Avatar>
  );
}
