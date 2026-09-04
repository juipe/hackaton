import { avatarTone, cn } from "@/lib/utils";

/** Размеры из макета: 34 в тесных строках, 44 в карточке группы. */
const SIZES = {
  sm: { root: "size-[34px]", text: "text-[13px]" },
  md: { root: "size-[44px]", text: "text-[15px]" },
} as const;

export type GroupAvatarSize = keyof typeof SIZES;

/**
 * Две буквы по значимым словам названия: «Квартира на Вайнера» → «КВ»,
 * «Хакатон Сбера» → «ХС». Предлоги и союзы (слова короче трёх букв)
 * пропускаются — иначе получилось бы «КН», и группы стали бы неразличимы.
 */
export function groupInitials(name: string): string {
  const words = (name ?? "").split(/\s+/).filter(Boolean);
  const meaningful = words.filter((word) => word.length > 2);
  const source = meaningful.length > 0 ? meaningful : words;
  return (
    source
      .slice(0, 2)
      .map((word) => word.slice(0, 1).toUpperCase())
      .join("") || "?"
  );
}

export interface GroupAvatarProps {
  group: { id: string; name: string };
  size?: GroupAvatarSize;
  className?: string;
}

export function GroupAvatar({ group, size = "md", className }: GroupAvatarProps) {
  const scale = SIZES[size] ?? SIZES.md;
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-badge font-bold",
        scale.root,
        scale.text,
        avatarTone(group.id),
        className,
      )}
      role="img"
      aria-label={group.name}
    >
      <span aria-hidden>{groupInitials(group.name)}</span>
    </span>
  );
}
