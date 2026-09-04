import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { ChevronsUpDown, LogOut, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { UserAvatar } from "@/components/common/UserAvatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger, } from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/useAuth";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
export function UserMenu({ variant = "compact", className }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [isSigningOut, setIsSigningOut] = useState(false);
    if (!user)
        return null;
    async function handleSignOut() {
        setIsSigningOut(true);
        try {
            await logout();
            navigate("/login", { replace: true });
        }
        catch (error) {
            toast.error(errorMessage(error));
        }
        finally {
            setIsSigningOut(false);
        }
    }
    return (_jsxs(DropdownMenu, { children: [_jsx(DropdownMenuTrigger, { asChild: true, children: _jsxs("button", { type: "button", "aria-label": "\u041C\u0435\u043D\u044E \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044F", className: cn("flex items-center rounded-full transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background", variant === "full"
                        ? "w-full min-w-0 gap-3 bg-card px-3.5 py-2.5 text-left shadow-flat hover:shadow-nav"
                        : "justify-center p-[3px]", // pads the 38px avatar up to a ~44px tap target
                    className), children: [_jsx(UserAvatar, { user: user, size: "md" }), variant === "full" ? (_jsxs(_Fragment, { children: [_jsxs("span", { className: "min-w-0 flex-1", children: [_jsx("span", { className: "block truncate text-[15px] font-semibold text-foreground", children: user.name }), _jsx("span", { className: "block truncate text-xs text-dim", children: user.email })] }), _jsx(ChevronsUpDown, { className: "size-4 shrink-0 text-dim", "aria-hidden": true })] })) : null] }) }), _jsxs(DropdownMenuContent, { align: "end", side: variant === "full" ? "top" : "bottom", className: "w-56", children: [_jsxs(DropdownMenuLabel, { className: "py-2", children: [_jsx("span", { className: "block truncate text-sm font-semibold text-foreground", children: user.name }), _jsx("span", { className: "block truncate text-xs font-normal text-dim", children: user.email })] }), _jsx(DropdownMenuSeparator, {}), _jsxs(DropdownMenuItem, { onSelect: () => navigate("/profile"), children: [_jsx(UserRound, { "aria-hidden": true }), "\u041F\u0440\u043E\u0444\u0438\u043B\u044C"] }), _jsxs(DropdownMenuItem, { destructive: true, disabled: isSigningOut, onSelect: (event) => {
                            event.preventDefault();
                            void handleSignOut();
                        }, children: [_jsx(LogOut, { "aria-hidden": true }), isSigningOut ? "Выходим…" : "Выйти"] })] })] }));
}
