import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface SectionCardProps {
  title: ReactNode;
  /** Надзаголовок над заголовком — капсом, мелко, приглушённо. */
  eyebrow?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  /**
   * Макет различает два размера H3: 19px на главной и 20px на странице группы.
   * По умолчанию 19px — передайте `text-[20px]` там, где нужен второй.
   */
  titleClassName?: string;
  /**
   * Подпись под заголовком бывает двух цветов: `text-muted-foreground` (по
   * умолчанию, страница группы) и `text-dim` (нижние карточки главной).
   */
  descriptionClassName?: string;
}

export function SectionCard({
  title,
  eyebrow,
  description,
  action,
  children,
  className,
  contentClassName,
  titleClassName,
  descriptionClassName,
}: SectionCardProps) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0 p-5 pb-4 sm:p-7 sm:pb-5">
        <div className="min-w-0 space-y-1">
          {eyebrow ? (
            <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
              {eyebrow}
            </p>
          ) : null}
          <CardTitle className={cn("text-[19px]", titleClassName)}>{title}</CardTitle>
          {description ? (
            <CardDescription className={descriptionClassName}>{description}</CardDescription>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </CardHeader>
      <CardContent className={cn("p-5 pt-0 sm:p-7 sm:pt-0", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}
