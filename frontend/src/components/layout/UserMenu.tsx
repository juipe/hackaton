import { ChevronsUpDown, LogOut, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { UserAvatar } from "@/components/common/UserAvatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/useAuth";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface UserMenuProps {
  /** `full` shows the name and email beside the avatar — used in the sidebar footer. */
  variant?: "compact" | "full";
  className?: string;
}

export function UserMenu({ variant = "compact", className }: UserMenuProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);

  if (!user) return null;

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setIsSigningOut(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Меню пользователя"
          className={cn(
            "flex items-center rounded-full transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            variant === "full"
              ? "w-full min-w-0 gap-3 bg-card px-3.5 py-2.5 text-left shadow-flat hover:shadow-nav"
              : "justify-center p-[3px]", // pads the 38px avatar up to a ~44px tap target
            className,
          )}
        >
          <UserAvatar user={user} size="md" />
          {variant === "full" ? (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-semibold text-foreground">
                  {user.name}
                </span>
                <span className="block truncate text-xs text-dim">{user.email}</span>
              </span>
              <ChevronsUpDown className="size-4 shrink-0 text-dim" aria-hidden />
            </>
          ) : null}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" side={variant === "full" ? "top" : "bottom"} className="w-56">
        <DropdownMenuLabel className="py-2">
          <span className="block truncate text-sm font-semibold text-foreground">
            {user.name}
          </span>
          <span className="block truncate text-xs font-normal text-dim">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/profile")}>
          <UserRound aria-hidden />
          Профиль
        </DropdownMenuItem>
        <DropdownMenuItem
          destructive
          disabled={isSigningOut}
          onSelect={(event) => {
            event.preventDefault();
            void handleSignOut();
          }}
        >
          <LogOut aria-hidden />
          {isSigningOut ? "Выходим…" : "Выйти"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
