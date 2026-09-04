import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { Mic, Plus } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAddExpense } from "@/components/layout/AddExpenseContext";
import { NAV_ITEMS } from "@/components/layout/NavItems";
import { UserMenu } from "@/components/layout/UserMenu";
import { useVoiceExpenseDialog } from "@/components/layout/VoiceExpenseDialogContext";
import { Wordmark } from "@/components/layout/Wordmark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroups } from "@/hooks/useGroups";
import { plural } from "@/lib/format";
import { formatMoneyRounded } from "@/lib/money";
import { cn } from "@/lib/utils";
const MAX_LISTED_GROUPS = 6;
/** Баланс в сайдбаре — беглый взгляд, поэтому без копеек и своим цветом. */
function balanceTone(cents) {
    if (cents > 0)
        return "text-positive";
    if (cents < 0)
        return "text-negative";
    return "text-dim";
}
function GroupLinks() {
    const { data: groups, isPending, isError } = useGroups();
    if (isPending) {
        return (_jsx("div", { className: "flex flex-col gap-2 px-[18px] py-1", children: [0, 1, 2].map((row) => (_jsx(Skeleton, { className: "h-5 w-full rounded-full" }, row))) }));
    }
    if (isError) {
        return (_jsx("p", { className: "px-[18px] py-1 text-[13px] text-dim", children: "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0433\u0440\u0443\u043F\u043F\u044B." }));
    }
    if (groups.length === 0) {
        return (_jsx("p", { className: "px-[18px] py-1 text-[13px] text-dim", children: "\u0413\u0440\u0443\u043F\u043F \u043F\u043E\u043A\u0430 \u043D\u0435\u0442 \u2014 \u0441\u043E\u0437\u0434\u0430\u0439\u0442\u0435 \u043F\u0435\u0440\u0432\u0443\u044E, \u0447\u0442\u043E\u0431\u044B \u0434\u0435\u043B\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434\u044B." }));
    }
    const listed = groups.slice(0, MAX_LISTED_GROUPS);
    return (_jsxs("ul", { className: "flex flex-col gap-0.5", children: [listed.map((group) => (_jsx("li", { children: _jsx(NavLink, { to: `/groups/${group.id}`, className: ({ isActive }) => cn("flex items-center gap-2.5 rounded-full px-[18px] py-[9px] transition-colors", isActive ? "bg-card shadow-flat" : "hover:bg-white/60"), children: ({ isActive }) => (_jsxs(_Fragment, { children: [_jsx("span", { className: cn("min-w-0 flex-1 truncate text-[15px] text-foreground", isActive && "font-semibold"), children: group.name }), _jsx("span", { className: cn("shrink-0 text-[13px] font-semibold tabular-nums-money", balanceTone(group.my_net_cents)), children: formatMoneyRounded(group.my_net_cents, { signed: true }) })] })) }) }, group.id))), groups.length > listed.length ? (_jsx("li", { children: _jsxs(NavLink, { to: "/groups", className: "block rounded-full px-[18px] py-[9px] text-[13px] font-semibold text-accent-foreground transition-colors hover:bg-white/60", children: ["\u0415\u0449\u0451 ", plural(groups.length - listed.length, "группа", "группы", "групп")] }) })) : null] }));
}
export function Sidebar() {
    const { openAddExpense } = useAddExpense();
    const { openVoiceExpense } = useVoiceExpenseDialog();
    return (_jsxs("aside", { className: "fixed inset-y-0 left-0 z-40 hidden w-[272px] flex-col gap-7 overflow-y-auto bg-app px-5 py-7 lg:flex", children: [_jsx("div", { className: "px-2", children: _jsx(Wordmark, {}) }), _jsxs("div", { className: "flex items-center gap-1.5", children: [_jsxs(Button, { size: "lg", className: "min-w-0 flex-1 gap-2.5 px-2 font-bold [&_svg]:size-[19px]", onClick: () => openAddExpense(), children: [_jsx(Plus, { "aria-hidden": true }), _jsx("span", { className: "truncate", children: "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434" })] }), _jsx(Button, { variant: "outline", size: "icon", className: "size-10 shrink-0", "aria-label": "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434 \u0433\u043E\u043B\u043E\u0441\u043E\u043C", title: "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434 \u0433\u043E\u043B\u043E\u0441\u043E\u043C", onClick: () => openVoiceExpense(), children: _jsx(Mic, { "aria-hidden": true }) })] }), _jsx("nav", { "aria-label": "\u041E\u0441\u043D\u043E\u0432\u043D\u0430\u044F \u043D\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u044F", className: "flex flex-col gap-1.5", children: NAV_ITEMS.map((item) => (_jsx(NavLink, { to: item.to, end: item.end, className: ({ isActive }) => cn("flex items-center gap-3.5 rounded-full px-[18px] py-[13px] text-base transition-colors", isActive
                        ? "bg-card font-semibold text-foreground shadow-nav"
                        : "font-medium text-muted-foreground hover:bg-white/60 hover:text-foreground"), children: ({ isActive }) => (_jsxs(_Fragment, { children: [_jsx(item.icon, { className: cn("size-5 shrink-0", isActive && "text-primary"), "aria-hidden": true }), item.label] })) }, item.to))) }), _jsxs("div", { className: "flex flex-col gap-2.5", children: [_jsxs("div", { className: "flex items-center justify-between gap-2 px-[18px]", children: [_jsx("h2", { className: "text-xs font-bold uppercase tracking-[0.09em] text-dim", children: "\u0412\u0430\u0448\u0438 \u0433\u0440\u0443\u043F\u043F\u044B" }), _jsx(NavLink, { to: "/groups/new", "aria-label": "\u0421\u043E\u0437\u0434\u0430\u0442\u044C \u0433\u0440\u0443\u043F\u043F\u0443", className: "flex size-[26px] shrink-0 items-center justify-center rounded-full bg-card text-accent-foreground shadow-flat transition-colors hover:bg-accent", children: _jsx(Plus, { className: "size-3.5", "aria-hidden": true }) })] }), _jsx(GroupLinks, {})] }), _jsx("div", { className: "mt-auto pt-2", children: _jsx(UserMenu, { variant: "full" }) })] }));
}
