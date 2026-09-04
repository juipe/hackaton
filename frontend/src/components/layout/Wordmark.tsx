import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

const SIZES = {
  /** Компактный — для мобильной шапки, где всего 56px высоты. */
  sm: { badge: "size-9", icon: "size-5", text: "text-[17px]", gap: "gap-2.5" },
  md: { badge: "size-11", icon: "size-6", text: "text-[20px]", gap: "gap-3" },
} as const;

export interface WordmarkProps {
  size?: keyof typeof SIZES;
  className?: string;
}

/** A circle cut in two: one shared total, split between people. */
export function Wordmark({ size = "md", className }: WordmarkProps) {
  const scale = SIZES[size] ?? SIZES.md;
  return (
    <Link
      to="/"
      className={cn("flex items-center text-foreground", scale.gap, className)}
    >
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-badge bg-primary text-primary-foreground",
          scale.badge,
        )}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className={scale.icon}
          aria-hidden
        >
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 3.5v17" />
          <path d="M3.5 12h8.5" strokeOpacity="0.45" />
        </svg>
      </span>
      <span className={cn("font-bold tracking-[-0.02em]", scale.text)}>Складчина</span>
    </Link>
  );
}
