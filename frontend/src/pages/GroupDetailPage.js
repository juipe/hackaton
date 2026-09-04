import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { ArrowLeft, ArrowLeftRight, Banknote, BarChart3, ListChecks, Scale, Sparkles, } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { BalanceCard } from "@/components/balances/BalanceCard";
import { BalanceList } from "@/components/balances/BalanceList";
import { DebtTransferList } from "@/components/balances/DebtTransferList";
import { PaymentList } from "@/components/balances/PaymentList";
import { SettleUpModal } from "@/components/balances/SettleUpModal";
import { SimplifyDebtsDialog } from "@/components/balances/SimplifyDebtsDialog";
import { BalanceBarChart } from "@/components/charts/BalanceBarChart";
import { CategoryChart } from "@/components/charts/CategoryChart";
import { MonthlySpendChart } from "@/components/charts/MonthlySpendChart";
import { ActivityFeed } from "@/components/common/ActivityFeed";
import { AvatarStack } from "@/components/common/AvatarStack";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { SectionCard } from "@/components/common/SectionCard";
import { AddExpenseDialog } from "@/components/expenses/AddExpenseDialog";
import { ExpenseList } from "@/components/expenses/ExpenseList";
import { VoiceExpenseDialog } from "@/components/expenses/VoiceExpenseDialog";
import { groupBalanceExplainer, transferCountCaption, } from "@/components/groups/balance-copy";
import { GroupSummaryHeader } from "@/components/groups/GroupSummaryHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGroupActivity } from "@/hooks/useActivity";
import { useCurrentUser } from "@/hooks/useAuth";
import { useBalances } from "@/hooks/useBalances";
import { useCategories } from "@/hooks/useCategories";
import { useSpendingByCategory, useSpendingOverTime } from "@/hooks/useDashboard";
import { useExpenses } from "@/hooks/useExpenses";
import { useGroup, useMembers } from "@/hooks/useGroups";
import { usePayments } from "@/hooks/usePayments";
import { ApiError } from "@/lib/api";
import { joinNames, plural } from "@/lib/format";
import { DEFAULT_CURRENCY, formatMoney, formatSigned } from "@/lib/money";
import { cn } from "@/lib/utils";
const TAB_VALUES = ["balances", "expenses", "analytics", "activity"];
/** Сколько имён показать под стопкой аватаров, прежде чем свернуть в «и ещё N». */
const MEMBERS_SHOWN = 3;
function isTabValue(value) {
    return value !== null && TAB_VALUES.includes(value);
}
function heroToneClass(cents) {
    if (cents > 0)
        return "text-positive";
    if (cents < 0)
        return "text-negative";
    return "text-foreground";
}
/** Надзаголовок карточки — капсом, мелко, приглушённо. */
function Eyebrow({ children }) {
    return (_jsx("p", { className: "text-[13px] font-bold uppercase tracking-[0.08em] text-dim", children: children }));
}
/** Обёртка для ошибки внутри блока страницы — в том же языке, что карточки. */
function ErrorCard({ error, onRetry }) {
    return (_jsx(Card, { className: "p-5 sm:p-7", children: _jsx(ErrorState, { error: error, onRetry: onRetry }) }));
}
/** A dead end for this group — wrong link, deleted group, or someone else's group. */
function GroupUnavailable({ error, hint, onRetry, }) {
    return (_jsx("div", { className: "py-10", children: _jsxs(Card, { className: "mx-auto max-w-md p-5 sm:p-8", children: [_jsx(ErrorState, { error: error, onRetry: onRetry }), hint ? (_jsx("p", { className: "mt-3 text-center text-sm text-muted-foreground", children: hint })) : null, _jsx("div", { className: "mt-5 flex justify-center", children: _jsx(Button, { asChild: true, variant: "outline", children: _jsxs(Link, { to: "/groups", children: [_jsx(ArrowLeft, {}), "\u041A \u0441\u043F\u0438\u0441\u043A\u0443 \u0433\u0440\u0443\u043F\u043F"] }) }) })] }) }));
}
export default function GroupDetailPage() {
    const { groupId } = useParams();
    const id = groupId ?? "";
    const currentUser = useCurrentUser();
    const [searchParams, setSearchParams] = useSearchParams();
    const [addOpen, setAddOpen] = useState(false);
    const [voiceOpen, setVoiceOpen] = useState(false);
    const [settleOpen, setSettleOpen] = useState(false);
    const [simplifyOpen, setSimplifyOpen] = useState(false);
    const [settlePrefill, setSettlePrefill] = useState(undefined);
    const [showSimplified, setShowSimplified] = useState(false);
    const groupQuery = useGroup(id);
    const membersQuery = useMembers(id);
    const balancesQuery = useBalances(id);
    const categoriesQuery = useCategories();
    const activityQuery = useGroupActivity(id, 30);
    const paymentsQuery = usePayments(id);
    // Only the server's `total` is wanted here, so ask for the smallest page possible.
    const expenseCountQuery = useExpenses(id, { limit: 1 });
    const categorySpendQuery = useSpendingByCategory({ period: "all", group_id: id });
    const overTimeQuery = useSpendingOverTime({ period: "all", group_id: id });
    const group = groupQuery.data;
    const balances = balancesQuery.data;
    const members = membersQuery.data ?? [];
    const categories = categoriesQuery.data ?? [];
    const currency = group?.currency ?? balances?.currency ?? DEFAULT_CURRENCY;
    const tabParam = searchParams.get("tab");
    const tab = isTabValue(tabParam) ? tabParam : "balances";
    const handleTabChange = (value) => {
        const next = new URLSearchParams(searchParams);
        if (value === "balances")
            next.delete("tab");
        else
            next.set("tab", value);
        setSearchParams(next, { replace: true });
    };
    const openSettle = (transfer) => {
        setSettlePrefill(transfer
            ? {
                fromUserId: transfer.from_user_id,
                toUserId: transfer.to_user_id,
                amountCents: transfer.amount_cents,
            }
            : undefined);
        setSettleOpen(true);
    };
    if (!groupId) {
        return (_jsx(GroupUnavailable, { error: new Error("Эта ссылка не ведёт ни на одну группу"), hint: "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0433\u0440\u0443\u043F\u043F\u0443 \u0438\u0437 \u0441\u043F\u0438\u0441\u043A\u0430, \u0447\u0442\u043E\u0431\u044B \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C." }));
    }
    if (groupQuery.isPending) {
        return _jsx(LoadingState, { label: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u0433\u0440\u0443\u043F\u043F\u0443\u2026", className: "py-20" });
    }
    if (groupQuery.isError || !group) {
        const status = groupQuery.error instanceof ApiError ? groupQuery.error.status : 0;
        if (status === 403) {
            return (_jsx(GroupUnavailable, { error: groupQuery.error, hint: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0433\u0440\u0443\u043F\u043F\u0443 \u043C\u043E\u0433\u0443\u0442 \u0442\u043E\u043B\u044C\u043A\u043E \u0435\u0451 \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u0438. \u041F\u043E\u043F\u0440\u043E\u0441\u0438\u0442\u0435 \u043A\u043E\u0433\u043E-\u043D\u0438\u0431\u0443\u0434\u044C \u0438\u0437 \u043D\u0438\u0445 \u043F\u0440\u0438\u0441\u043B\u0430\u0442\u044C \u0432\u0430\u043C \u043F\u0440\u0438\u0433\u043B\u0430\u0448\u0435\u043D\u0438\u0435." }));
        }
        if (status === 404) {
            return (_jsx(GroupUnavailable, { error: groupQuery.error, hint: "\u0413\u0440\u0443\u043F\u043F\u0430 \u0443\u0434\u0430\u043B\u0435\u043D\u0430, \u043B\u0438\u0431\u043E \u0430\u0434\u0440\u0435\u0441 \u0443\u0441\u0442\u0430\u0440\u0435\u043B." }));
        }
        return (_jsx(GroupUnavailable, { error: groupQuery.error, onRetry: () => void groupQuery.refetch() }));
    }
    const pairwiseCount = balances?.pairwise.length ?? 0;
    const simplifiedCount = balances?.simplified.length ?? 0;
    const transfers = showSimplified ? (balances?.simplified ?? []) : (balances?.pairwise ?? []);
    // The group payload already carries both figures, so the hero is correct while
    // the (heavier) balances query is still in flight and simply sharpens afterwards.
    const myNet = balances?.me.net_cents ?? group.my_net_cents;
    const totalSpending = balances?.total_spending_cents ?? group.total_spending_cents;
    const myShare = balances?.me.owed_cents ?? 0;
    const expenseCount = expenseCountQuery.data?.total ?? 0;
    // Доля считается только когда есть от чего её считать — придумывать 0% не надо.
    const sharePercent = totalSpending > 0 ? Math.round((myShare / totalSpending) * 100) : null;
    const memberUsers = members.map((member) => member.user);
    return (_jsxs("div", { className: "flex flex-col gap-6 pb-2", children: [_jsxs(Link, { to: "/groups", className: "inline-flex w-fit items-center gap-2 rounded-full bg-card py-2 pl-3 pr-4 text-sm font-semibold text-muted-foreground shadow-flat transition-colors hover:text-foreground", children: [_jsx(ArrowLeft, { className: "size-4 shrink-0", "aria-hidden": "true" }), "\u0412\u0441\u0435 \u0433\u0440\u0443\u043F\u043F\u044B"] }), _jsx(GroupSummaryHeader, { group: group, onAddExpense: () => setAddOpen(true), onVoiceExpense: () => setVoiceOpen(true) }), balancesQuery.isError && !balances ? (_jsx(ErrorCard, { error: balancesQuery.error, onRetry: () => void balancesQuery.refetch() })) : balancesQuery.isPending ? (_jsxs("div", { className: "grid gap-5 lg:grid-cols-[1.65fr_1fr]", children: [_jsx(Skeleton, { className: "h-[300px] rounded-card" }), _jsx(Skeleton, { className: "h-[300px] rounded-card" })] })) : (_jsxs("div", { className: "grid gap-5 lg:grid-cols-[1.65fr_1fr]", children: [_jsxs(Card, { className: "flex min-w-0 flex-col gap-6 p-5 sm:p-7 lg:gap-7 lg:p-8", children: [_jsxs("div", { children: [_jsx(Eyebrow, { children: "\u0412\u0430\u0448 \u0431\u0430\u043B\u0430\u043D\u0441 \u0432 \u0433\u0440\u0443\u043F\u043F\u0435" }), _jsx("p", { className: cn("mt-2.5 break-words text-[40px] font-bold leading-none tracking-[-0.035em] tabular-nums-money lg:text-[60px]", heroToneClass(myNet)), children: formatSigned(myNet, currency) }), _jsx("p", { className: "mt-3 text-base text-muted-foreground", children: groupBalanceExplainer(myNet, pairwiseCount, simplifiedCount) })] }), _jsxs("div", { className: "grid grid-cols-1 gap-3 min-[420px]:grid-cols-2", children: [_jsx(BalanceCard, { label: "\u0412\u044B \u0437\u0430\u043F\u043B\u0430\u0442\u0438\u043B\u0438", cents: balances?.me.paid_cents ?? 0, currency: currency, tone: "neutral" }), _jsx(BalanceCard, { label: "\u0412\u0430\u0448\u0430 \u0434\u043E\u043B\u044F", cents: myShare, currency: currency, tone: "neutral" })] }), _jsxs("div", { className: "flex flex-wrap items-center gap-2.5", children: [_jsxs(Button, { className: "h-12 flex-1 sm:flex-none", onClick: () => openSettle(), children: [_jsx(ArrowLeftRight, {}), "\u041F\u043E\u0433\u0430\u0441\u0438\u0442\u044C \u0434\u043E\u043B\u0433"] }), _jsxs(Button, { variant: "secondary", className: "h-12 flex-1 sm:flex-none", onClick: () => setSimplifyOpen(true), children: [_jsx(Sparkles, {}), "\u0423\u043F\u0440\u043E\u0441\u0442\u0438\u0442\u044C \u0434\u043E\u043B\u0433\u0438"] })] })] }), _jsxs(Card, { className: "flex min-w-0 flex-col p-5 sm:p-7 lg:p-8", children: [_jsx(Eyebrow, { children: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u0433\u0440\u0443\u043F\u043F\u044B" }), _jsx("p", { className: "mt-2.5 break-words text-[28px] font-bold leading-[1.1] tracking-[-0.03em] tabular-nums-money lg:text-[34px]", children: formatMoney(totalSpending, currency) }), _jsxs("p", { className: "mt-1.5 text-[15px] text-muted-foreground", children: [plural(expenseCount, "расход", "расхода", "расходов"), " \u00B7 \u0437\u0430 \u0432\u0441\u0451 \u0432\u0440\u0435\u043C\u044F"] }), _jsxs("div", { className: "mt-auto pt-7", children: [sharePercent !== null ? (_jsxs(_Fragment, { children: [_jsx("div", { className: "h-2 overflow-hidden rounded-full bg-muted", children: _jsx("div", { className: "h-full rounded-full bg-primary", style: { width: `${Math.min(100, sharePercent)}%` } }) }), _jsxs("p", { className: "mt-3 text-sm text-muted-foreground", children: ["\u0412\u0430\u0448\u0430 \u0434\u043E\u043B\u044F \u2014", " ", _jsxs("span", { className: "font-semibold text-foreground tabular-nums-money", children: [sharePercent, "%"] }), " ", "\u043E\u0442 \u0432\u0441\u0435\u0445 \u0440\u0430\u0441\u0445\u043E\u0434\u043E\u0432"] })] })) : null, memberUsers.length > 0 ? (_jsxs("div", { className: "mt-5 flex items-center gap-2.5", children: [_jsx(AvatarStack, { users: memberUsers, size: "sm", max: MEMBERS_SHOWN }), _jsx("span", { className: "min-w-0 truncate text-sm text-dim", children: joinNames(memberUsers.map((user) => user.name), MEMBERS_SHOWN) })] })) : null] })] })] })), _jsxs(Tabs, { value: tab, onValueChange: handleTabChange, children: [_jsx("div", { className: "no-scrollbar -my-1 snap-x snap-mandatory overflow-x-auto scroll-px-4 py-1", children: _jsxs(TabsList, { className: "w-max", children: [_jsxs(TabsTrigger, { value: "balances", className: "snap-start", children: [_jsx(Scale, { "aria-hidden": "true" }), "\u0411\u0430\u043B\u0430\u043D\u0441\u044B"] }), _jsxs(TabsTrigger, { value: "expenses", className: "snap-start", children: [_jsx(Banknote, { "aria-hidden": "true" }), "\u0420\u0430\u0441\u0445\u043E\u0434\u044B"] }), _jsxs(TabsTrigger, { value: "analytics", className: "snap-start", children: [_jsx(BarChart3, { "aria-hidden": "true" }), "\u0410\u043D\u0430\u043B\u0438\u0442\u0438\u043A\u0430"] }), _jsxs(TabsTrigger, { value: "activity", className: "snap-start", children: [_jsx(ListChecks, { "aria-hidden": "true" }), "\u0421\u043E\u0431\u044B\u0442\u0438\u044F"] })] }) }), _jsxs(TabsContent, { value: "balances", className: "flex flex-col gap-5", children: [balancesQuery.isPending ? (_jsx(LoadingState, { label: "\u0421\u0447\u0438\u0442\u0430\u0435\u043C, \u043A\u0442\u043E \u043A\u043E\u043C\u0443 \u0434\u043E\u043B\u0436\u0435\u043D\u2026" })) : balancesQuery.isError || !balances ? (_jsx(ErrorCard, { error: balancesQuery.error, onRetry: () => void balancesQuery.refetch() })) : (_jsxs("div", { className: "grid items-start gap-5 lg:grid-cols-[1.15fr_1fr]", children: [_jsxs(SectionCard, { titleClassName: "text-[20px]", className: "min-w-0", title: "\u041A\u0442\u043E \u043A\u043E\u043C\u0443 \u0434\u043E\u043B\u0436\u0435\u043D", description: showSimplified
                                            ? "Минимум переводов, которые закрывают всё. Итоговый баланс ни у кого не меняется — меняется только маршрут денег."
                                            : "Все долги ровно так, как их создали расходы, — взаимозачётом внутри каждой пары.", action: _jsxs("div", { className: "flex shrink-0 items-center gap-2.5", children: [_jsx(Label, { htmlFor: "simplify-debts", className: "whitespace-nowrap text-[13px] font-semibold text-muted-foreground", children: "\u0423\u043F\u0440\u043E\u0441\u0442\u0438\u0442\u044C" }), _jsx(Switch, { id: "simplify-debts", checked: showSimplified, onCheckedChange: setShowSimplified })] }), children: [_jsx("p", { className: "mb-3.5 text-[13px] text-dim", children: transferCountCaption(pairwiseCount, simplifiedCount) }), _jsx(DebtTransferList, { transfers: transfers, currency: currency, currentUserId: currentUser.id, onSettle: openSettle })] }), _jsx(SectionCard, { titleClassName: "text-[20px]", className: "min-w-0", title: "\u0411\u0430\u043B\u0430\u043D\u0441\u044B \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u043E\u0432", description: "\u041F\u043E\u043B\u043E\u0436\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0435 \u0447\u0438\u0441\u043B\u043E \u0437\u043D\u0430\u0447\u0438\u0442, \u0447\u0442\u043E \u0433\u0440\u0443\u043F\u043F\u0430 \u0434\u043E\u043B\u0436\u043D\u0430 \u044D\u0442\u043E\u043C\u0443 \u0447\u0435\u043B\u043E\u0432\u0435\u043A\u0443.", children: _jsx(BalanceList, { balances: balances.balances, currency: currency, currentUserId: currentUser.id }) })] })), _jsx(SectionCard, { className: "min-w-0", title: "\u041F\u0435\u0440\u0435\u0432\u043E\u0434\u044B", description: "\u0420\u0430\u0441\u0447\u0451\u0442\u044B, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u0438 \u0443\u0436\u0435 \u0437\u0430\u043F\u0438\u0441\u0430\u043B\u0438, \u2014 \u043E\u0442 \u0441\u0430\u043C\u043E\u0433\u043E \u0441\u0432\u0435\u0436\u0435\u0433\u043E.", children: paymentsQuery.isPending ? (_jsx(LoadingState, { label: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u043F\u0435\u0440\u0435\u0432\u043E\u0434\u044B\u2026" })) : paymentsQuery.isError ? (_jsx(ErrorState, { error: paymentsQuery.error, onRetry: () => void paymentsQuery.refetch() })) : (_jsx(PaymentList, { payments: paymentsQuery.data, currency: currency, currentUserId: currentUser.id })) })] }), _jsx(TabsContent, { value: "expenses", children: membersQuery.isPending || categoriesQuery.isPending ? (_jsx(LoadingState, { label: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u0440\u0430\u0441\u0445\u043E\u0434\u044B\u2026" })) : membersQuery.isError || categoriesQuery.isError ? (_jsx(ErrorCard, { error: membersQuery.error ?? categoriesQuery.error, onRetry: () => {
                                void membersQuery.refetch();
                                void categoriesQuery.refetch();
                            } })) : (_jsx(ExpenseList, { groupId: group.id, members: members, categories: categories, currentUserId: currentUser.id })) }), _jsxs(TabsContent, { value: "analytics", className: "flex flex-col gap-5", children: [_jsxs("div", { className: "grid gap-5 lg:grid-cols-2", children: [_jsx(SectionCard, { titleClassName: "text-[20px]", className: "min-w-0", title: "\u041A\u0443\u0434\u0430 \u0443\u0448\u043B\u0438 \u0434\u0435\u043D\u044C\u0433\u0438", description: "\u0412\u0441\u0435 \u0440\u0430\u0441\u0445\u043E\u0434\u044B \u0433\u0440\u0443\u043F\u043F\u044B \u00B7 \u0437\u0430 \u0432\u0441\u0451 \u0432\u0440\u0435\u043C\u044F", children: categorySpendQuery.isError ? (_jsx(ErrorState, { error: categorySpendQuery.error, onRetry: () => void categorySpendQuery.refetch() })) : (_jsx(CategoryChart, { data: categorySpendQuery.data, currency: currency, isLoading: categorySpendQuery.isPending })) }), _jsx(SectionCard, { titleClassName: "text-[20px]", className: "min-w-0", title: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u043F\u043E \u043C\u0435\u0441\u044F\u0446\u0430\u043C", description: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u0433\u0440\u0443\u043F\u043F\u044B \u043C\u0435\u0441\u044F\u0446 \u0437\u0430 \u043C\u0435\u0441\u044F\u0446\u0435\u043C.", children: overTimeQuery.isError ? (_jsx(ErrorState, { error: overTimeQuery.error, onRetry: () => void overTimeQuery.refetch() })) : (_jsx(MonthlySpendChart, { data: overTimeQuery.data, currency: currency, isLoading: overTimeQuery.isPending })) })] }), _jsx(SectionCard, { titleClassName: "text-[20px]", title: "\u0411\u0430\u043B\u0430\u043D\u0441 \u043F\u043E \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u0430\u043C", description: "\u0412\u044B\u0448\u0435 \u043D\u0443\u043B\u044F \u2014 \u0434\u0435\u043D\u044C\u0433\u0438, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u0434\u043E\u043B\u0436\u043D\u044B \u0447\u0435\u043B\u043E\u0432\u0435\u043A\u0443, \u043D\u0438\u0436\u0435 \u2014 \u0442\u0435, \u0447\u0442\u043E \u0434\u043E\u043B\u0436\u0435\u043D \u043E\u043D.", children: balancesQuery.isError ? (_jsx(ErrorState, { error: balancesQuery.error, onRetry: () => void balancesQuery.refetch() })) : (_jsx(BalanceBarChart, { balances: balances?.balances, currency: currency, currentUserId: currentUser.id, isLoading: balancesQuery.isPending })) })] }), _jsx(TabsContent, { value: "activity", children: _jsx(SectionCard, { titleClassName: "text-[20px]", title: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u0441\u043E\u0431\u044B\u0442\u0438\u044F", description: "\u0412\u0441\u0435 \u0438\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u044F, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u0432\u043D\u043E\u0441\u0438\u043B\u0438 \u0432 \u044D\u0442\u043E\u0439 \u0433\u0440\u0443\u043F\u043F\u0435.", children: _jsx(ActivityFeed, { activities: activityQuery.data, isLoading: activityQuery.isPending, error: activityQuery.error, emptyLabel: "\u041F\u043E\u043A\u0430 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043F\u0440\u043E\u0438\u0441\u0445\u043E\u0434\u0438\u043B\u043E" }) }) })] }), _jsx(AddExpenseDialog, { open: addOpen, onOpenChange: setAddOpen, groupId: group.id }), _jsx(VoiceExpenseDialog, { open: voiceOpen, onOpenChange: setVoiceOpen, groupId: group.id }), _jsx(SettleUpModal, { open: settleOpen, onOpenChange: setSettleOpen, group: group, members: members, balances: balances, prefill: settlePrefill }), _jsx(SimplifyDebtsDialog, { open: simplifyOpen, onOpenChange: setSimplifyOpen, group: group, currentUserId: currentUser.id })] }));
}
