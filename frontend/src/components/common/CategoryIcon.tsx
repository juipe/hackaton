import {
  Car,
  CircleEllipsis,
  Film,
  HeartPulse,
  Home,
  KeyRound,
  Plane,
  Repeat,
  ShoppingBag,
  ShoppingCart,
  UtensilsCrossed,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Explicit lookup rather than indexing the lucide namespace: importing the whole
 * icon set would pull ~1,500 components into the bundle and defeat tree-shaking.
 * Keys are the PascalCase names stored in `Category.icon`.
 */
const CATEGORY_ICONS: Record<string, LucideIcon> = {
  UtensilsCrossed,
  ShoppingCart,
  Home,
  KeyRound,
  Zap,
  Car,
  Plane,
  Film,
  ShoppingBag,
  HeartPulse,
  Repeat,
  CircleEllipsis,
};

/**
 * `inline` — голая иконка внутри чипа или строки селекта (поведение по умолчанию,
 * чтобы вызовы вне списка расходов остались собой). `sm` и `md` — плитка нового
 * языка: квадрат со скруглением поля, иконка по центру.
 */
export type CategoryIconSize = "inline" | "sm" | "md";

/** Тон плитки: обычный расход — нейтральный, «платили вы» — зелёный. */
export type CategoryIconTone = "muted" | "accent";

const TILE_SIZE: Record<"sm" | "md", string> = {
  sm: "size-10 [&>svg]:size-5",
  md: "size-[46px] [&>svg]:size-[22px]",
};

const TILE_TONE: Record<CategoryIconTone, string> = {
  muted: "bg-muted text-muted-foreground",
  accent: "bg-accent text-accent-foreground",
};

export interface CategoryIconProps {
  name: string;
  className?: string;
  size?: CategoryIconSize;
  tone?: CategoryIconTone;
}

export function CategoryIcon({
  name,
  className,
  size = "inline",
  tone = "muted",
}: CategoryIconProps) {
  const Icon = (name && CATEGORY_ICONS[name]) || CircleEllipsis;

  if (size === "inline") {
    return <Icon className={cn("size-4 shrink-0", className)} aria-hidden />;
  }

  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-field",
        TILE_SIZE[size],
        TILE_TONE[tone],
        className,
      )}
    >
      <Icon aria-hidden />
    </span>
  );
}
