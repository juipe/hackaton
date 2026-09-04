import { Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ConfirmButtonProps {
  title: string;
  description?: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  children: ReactNode;
  destructive?: boolean;
}

export function ConfirmButton({
  title,
  description,
  confirmLabel = "Подтвердить",
  onConfirm,
  children,
  destructive = false,
}: ConfirmButtonProps) {
  const [open, setOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);

  async function handleConfirm() {
    setIsPending(true);
    try {
      await onConfirm();
      setOpen(false);
    } catch {
      // The caller owns the failure message (toast.error), and the dialog stays
      // open so the person can read it and try again.
    } finally {
      setIsPending(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(next) => (isPending ? undefined : setOpen(next))}>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description ? (
            <AlertDialogDescription>{description}</AlertDialogDescription>
          ) : null}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Отмена</AlertDialogCancel>
          <AlertDialogAction
            disabled={isPending}
            className={cn(
              // Зелёная подсветка примитива под красной кнопкой читалась бы как
              // грязь, поэтому опасное действие гасит её явно.
              destructive && buttonVariants({ variant: "destructive" }),
              "gap-2",
            )}
            onClick={(event) => {
              // Keep the dialog mounted until the promise settles.
              event.preventDefault();
              void handleConfirm();
            }}
          >
            {isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
