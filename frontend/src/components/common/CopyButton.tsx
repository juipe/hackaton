import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * `navigator.clipboard` only exists in a secure context, and `http://<lan-ip>` is
 * not one — so the legacy selection path stays as a fallback for anyone opening
 * the app from another device on the network.
 */
function copyWithTextarea(value: string): boolean {
  if (typeof document === "undefined") return false;

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);

  const selection = document.getSelection();
  const previousRange =
    selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

  textarea.select();
  textarea.setSelectionRange(0, value.length);

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  }

  document.body.removeChild(textarea);
  if (selection && previousRange) {
    selection.removeAllRanges();
    selection.addRange(previousRange);
  }
  return copied;
}

async function writeToClipboard(value: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Permission denied or an insecure origin — fall through to the fallback.
    }
  }
  return copyWithTextarea(value);
}

export interface CopyButtonProps {
  value: string;
  label?: string;
  className?: string;
}

export function CopyButton({ value, label = "Скопировать", className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function handleCopy() {
    const ok = await writeToClipboard(value);
    if (ok) {
      setCopied(true);
      toast.success("Скопировано в буфер обмена");
    } else {
      toast.error("Не удалось скопировать — выделите текст и скопируйте вручную");
    }
  }

  return (
    <Button
      type="button"
      // Капсула меняет вариант, а не только иконку: зелёная плашка держится
      // ровно те две секунды, пока «Скопировано» ещё правда.
      variant={copied ? "soft" : "outline"}
      size="sm"
      className={cn("shrink-0", className)}
      onClick={() => void handleCopy()}
    >
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      {copied ? "Скопировано" : label}
    </Button>
  );
}
