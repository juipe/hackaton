import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { LogOut, UserMinus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ConfirmButton } from "@/components/common/ConfirmButton";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useRemoveMember } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
export function MemberList({ group, members, currentUserId }) {
    const navigate = useNavigate();
    const removeMember = useRemoveMember(group.id);
    const [refusal, setRefusal] = useState(null);
    const viewerIsOwner = group.my_role === "owner";
    async function handleRemove(member, leaving) {
        setRefusal(null);
        try {
            await removeMember.mutateAsync(member.user.id);
            if (leaving) {
                toast.success(`Вы вышли из группы «${group.name}»`);
                navigate("/groups");
                return;
            }
            toast.success(`Участник ${member.user.name} удалён из группы «${group.name}»`);
        }
        catch (error) {
            // The server's wording is the instruction the user needs — it explains which
            // debt is in the way — so it is kept verbatim and pinned to the row it belongs
            // to, not just flashed in a toast.
            const message = errorMessage(error);
            setRefusal({ userId: member.user.id, message });
            toast.error(message);
        }
    }
    if (members.length === 0) {
        return (_jsx("p", { className: "px-3 py-2 text-[15px] text-muted-foreground", children: "\u0423\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442. \u041F\u0440\u0438\u0433\u043B\u0430\u0441\u0438\u0442\u0435 \u043A\u043E\u0433\u043E-\u043D\u0438\u0431\u0443\u0434\u044C, \u0447\u0442\u043E\u0431\u044B \u0434\u0435\u043B\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434\u044B \u0432\u043C\u0435\u0441\u0442\u0435." }));
    }
    return (_jsx("ul", { className: "flex flex-col gap-0.5", children: members.map((member) => {
            const isSelf = member.user.id === currentUserId;
            const isOwnerRow = member.role === "owner";
            const canRemove = viewerIsOwner && !isSelf && !isOwnerRow;
            const canLeave = isSelf && !isOwnerRow;
            return (_jsxs("li", { children: [_jsxs("div", { className: "flex items-center gap-3.5 rounded-row px-3 py-3 transition-colors hover:bg-subtle sm:px-4", children: [_jsx(UserAvatar, { user: member.user, size: "lg", className: "shrink-0" }), _jsxs("div", { className: "min-w-0 flex-1", children: [_jsxs("div", { className: "flex flex-wrap items-center gap-x-2 gap-y-1", children: [_jsx("span", { className: "truncate text-base font-semibold text-foreground", children: member.user.name }), _jsx(Badge, { variant: isOwnerRow ? "default" : "neutral", children: isOwnerRow ? "Владелец" : "Участник" }), isSelf ? _jsx(Badge, { variant: "neutral", children: "\u0412\u044B" }) : null] }), _jsxs("p", { className: "mt-0.5 break-words text-[13px] text-dim sm:truncate", children: [member.user.email, " \u00B7 \u0432 \u0433\u0440\u0443\u043F\u043F\u0435 \u0441 ", formatDate(member.joined_at)] })] }), canRemove ? (_jsx(ConfirmButton, { title: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u0430 \u0438\u0437 \u0433\u0440\u0443\u043F\u043F\u044B?", description: `Участник: ${member.user.name}. Доступ к группе «${group.name}» будет закрыт. Расходы, которые уже оплачены, останутся в истории группы.`, confirmLabel: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u0430", destructive: true, onConfirm: () => handleRemove(member, false), children: _jsxs(Button, { variant: "ghost", size: "sm", className: "h-11 shrink-0 hover:bg-negative-surface hover:text-negative", disabled: removeMember.isPending, "aria-label": `Удалить участника из группы: ${member.user.name}`, children: [_jsx(UserMinus, { "aria-hidden": "true" }), _jsx("span", { className: "hidden sm:inline", children: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C" })] }) })) : canLeave ? (_jsx(ConfirmButton, { title: `Выйти из группы «${group.name}»?`, description: "\u0412\u044B \u043F\u0435\u0440\u0435\u0441\u0442\u0430\u043D\u0435\u0442\u0435 \u0432\u0438\u0434\u0435\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434\u044B \u044D\u0442\u043E\u0439 \u0433\u0440\u0443\u043F\u043F\u044B. \u0412\u0430\u0441 \u043C\u043E\u0436\u043D\u043E \u0431\u0443\u0434\u0435\u0442 \u043F\u0440\u0438\u0433\u043B\u0430\u0441\u0438\u0442\u044C \u0441\u043D\u043E\u0432\u0430, \u0430 \u043F\u0440\u043E\u0448\u043B\u044B\u0435 \u0440\u0430\u0441\u0445\u043E\u0434\u044B \u043E\u0441\u0442\u0430\u043D\u0443\u0442\u0441\u044F \u0432 \u0433\u0440\u0443\u043F\u043F\u0435.", confirmLabel: "\u0412\u044B\u0439\u0442\u0438 \u0438\u0437 \u0433\u0440\u0443\u043F\u043F\u044B", destructive: true, onConfirm: () => handleRemove(member, true), children: _jsxs(Button, { variant: "outline", size: "sm", className: "h-11 shrink-0", disabled: removeMember.isPending, "aria-label": `Выйти из группы «${group.name}»`, children: [_jsx(LogOut, { "aria-hidden": "true" }), _jsx("span", { className: "hidden sm:inline", children: "\u0412\u044B\u0439\u0442\u0438" })] }) })) : isSelf && isOwnerRow ? (_jsx("span", { className: "hidden max-w-[11rem] shrink-0 text-right text-[13px] leading-snug text-dim lg:block", children: "\u0412\u043B\u0430\u0434\u0435\u043B\u0435\u0446 \u043E\u0441\u0442\u0430\u0451\u0442\u0441\u044F \u0432 \u0433\u0440\u0443\u043F\u043F\u0435 \u2014 \u0435\u0451 \u043C\u043E\u0436\u043D\u043E \u0442\u043E\u043B\u044C\u043A\u043E \u0443\u0434\u0430\u043B\u0438\u0442\u044C" })) : null] }), refusal?.userId === member.user.id ? (_jsx(Alert, { variant: "destructive", className: "mx-3 mb-2 mt-1 w-auto sm:mx-4", children: _jsx(AlertDescription, { children: refusal.message }) })) : null] }, member.id));
        }) }));
}
