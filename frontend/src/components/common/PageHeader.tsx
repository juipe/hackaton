import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  title: string;
  /** Надзаголовок над H1 — капсом, мелко, приглушённо. */
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string };
  className?: string;
}

export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  back,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {back ? (
        <Link
          to={back.to}
          className="inline-flex w-fit items-center gap-2 rounded-full bg-card py-2 pl-3 pr-4 text-sm font-semibold text-muted-foreground shadow-flat transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4 shrink-0" aria-hidden />
          {back.label}
        </Link>
      ) : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
        <div className="min-w-0 space-y-1">
          {eyebrow ? (
            <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-[28px] font-bold leading-[1.15] tracking-[-0.025em] text-foreground [overflow-wrap:anywhere] lg:text-[34px] lg:leading-10">
            {title}
          </h1>
          {description ? (
            <div className="text-base text-muted-foreground [overflow-wrap:anywhere]">
              {description}
            </div>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-wrap items-center gap-2 sm:shrink-0">{actions}</div>
        ) : null}
      </div>
    </div>
  );
}
