import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { CalendarRange, ChevronDown, ChevronLeft, ChevronRight, Receipt, Search, SearchX, X, } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ExpenseCard } from "@/components/expenses/ExpenseCard";
import { ExpenseDetailDialog } from "@/components/expenses/ExpenseDetailDialog";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger, } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useExpenses } from "@/hooks/useExpenses";
import { formatDateShort, formatDayHeading, toDateInputValue } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
const PAGE_SIZE = 20;
const ANY = "any";
/**
 * Группировка идёт по уже полученной странице и только по соседним элементам:
 * порядок, в котором расходы пришли с сервера, сохраняется как есть. Если день
 * вдруг встретится дважды, он и покажется дважды — это честнее, чем молча
 * пересортировать список под свою вёрстку.
 */
function groupByDay(items) {
    const groups = [];
    for (const expense of items) {
        const key = toDateInputValue(expense.occurred_at);
        const last = groups[groups.length - 1];
        if (last && last.key === key) {
            last.items.push(expense);
            last.totalCents += expense.amount_cents;
            continue;
        }
        groups.push({
            key,
            date: expense.occurred_at,
            totalCents: expense.amount_cents,
            currency: expense.currency,
            items: [expense],
        });
    }
    return groups;
}
export function ExpenseList({ groupId, members, categories, currentUserId, }) {
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [categoryId, setCategoryId] = useState(ANY);
    const [payerId, setPayerId] = useState(ANY);
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [page, setPage] = useState(0);
    const [selectedId, setSelectedId] = useState(undefined);
    useEffect(() => {
        const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
        return () => window.clearTimeout(timer);
    }, [search]);
    // A filter change makes the current page number meaningless.
    useEffect(() => {
        setPage(0);
    }, [debouncedSearch, categoryId, payerId, dateFrom, dateTo]);
    const filters = useMemo(() => ({
        q: debouncedSearch || undefined,
        category_id: categoryId === ANY ? undefined : categoryId,
        paid_by: payerId === ANY ? undefined : payerId,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
    }), [debouncedSearch, categoryId, payerId, dateFrom, dateTo, page]);
    const expensesQuery = useExpenses(groupId, filters);
    const pageData = expensesQuery.data;
    const items = pageData?.items ?? [];
    const total = pageData?.total ?? 0;
    const days = useMemo(() => groupByDay(items), [items]);
    const periodActive = Boolean(dateFrom) || Boolean(dateTo);
    const filtersActive = Boolean(search) ||
        Boolean(debouncedSearch) ||
        categoryId !== ANY ||
        payerId !== ANY ||
        periodActive;
    const clearFilters = () => {
        setSearch("");
        setDebouncedSearch("");
        setCategoryId(ANY);
        setPayerId(ANY);
        setDateFrom("");
        setDateTo("");
        setPage(0);
    };
    const firstShown = total === 0 ? 0 : page * PAGE_SIZE + 1;
    const lastShown = page * PAGE_SIZE + items.length;
    return (_jsxs("div", { className: "flex flex-col gap-4", children: [_jsxs("div", { className: "no-scrollbar flex snap-x snap-proximity items-center gap-2 overflow-x-auto scroll-px-4 py-1 lg:flex-wrap lg:overflow-x-visible lg:snap-none", children: [_jsxs("label", { className: "inline-flex h-[46px] w-[220px] shrink-0 snap-start items-center gap-2.5 rounded-full bg-card px-[18px] shadow-flat sm:w-[260px]", children: [_jsx(Search, { className: "size-[18px] shrink-0 text-dim", "aria-hidden": "true" }), _jsx("input", { type: "search", value: search, onChange: (event) => setSearch(event.target.value), placeholder: "\u041F\u043E\u0438\u0441\u043A \u043F\u043E \u0440\u0430\u0441\u0445\u043E\u0434\u0430\u043C", "aria-label": "\u041F\u043E\u0438\u0441\u043A \u043F\u043E \u0440\u0430\u0441\u0445\u043E\u0434\u0430\u043C", className: "h-full w-full min-w-0 border-0 bg-transparent p-0 text-[15px] text-foreground outline-none placeholder:text-dim" })] }), _jsxs(FilterCapsule, { value: categoryId, onValueChange: setCategoryId, label: "\u0424\u0438\u043B\u044C\u0442\u0440 \u043F\u043E \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u0438", clearLabel: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0444\u0438\u043B\u044C\u0442\u0440 \u043F\u043E \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u0438", children: [_jsx(SelectItem, { value: ANY, children: "\u0412\u0441\u0435 \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u0438" }), categories.map((category) => (_jsx(SelectItem, { value: category.id, children: category.name }, category.id)))] }), _jsxs(FilterCapsule, { value: payerId, onValueChange: setPayerId, label: "\u0424\u0438\u043B\u044C\u0442\u0440 \u043F\u043E \u043F\u043B\u0430\u0442\u0435\u043B\u044C\u0449\u0438\u043A\u0443", clearLabel: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0444\u0438\u043B\u044C\u0442\u0440 \u043F\u043E \u043F\u043B\u0430\u0442\u0435\u043B\u044C\u0449\u0438\u043A\u0443", children: [_jsx(SelectItem, { value: ANY, children: "\u041B\u044E\u0431\u043E\u0439 \u043F\u043B\u0430\u0442\u0435\u043B\u044C\u0449\u0438\u043A" }), members.map((member) => (_jsx(SelectItem, { value: member.user.id, children: member.user.id === currentUserId ? "Вы" : member.user.name }, member.id)))] }), _jsx(PeriodCapsule, { dateFrom: dateFrom, dateTo: dateTo, onDateFromChange: setDateFrom, onDateToChange: setDateTo }), filtersActive ? (_jsxs(Button, { variant: "ghost", className: "h-[46px] shrink-0 snap-start px-4 text-[15px] font-medium text-dim hover:bg-transparent hover:text-foreground [&_svg]:size-[15px]", onClick: clearFilters, children: [_jsx(X, { strokeWidth: 2.2, "aria-hidden": "true" }), "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0444\u0438\u043B\u044C\u0442\u0440\u044B"] })) : null] }), expensesQuery.isPending ? (_jsx("div", { className: "flex flex-col gap-2", "aria-busy": "true", children: [0, 1, 2, 3].map((row) => (_jsx(Skeleton, { className: "h-[74px] w-full rounded-row" }, row))) })) : expensesQuery.isError ? (_jsx(ErrorState, { error: expensesQuery.error, onRetry: () => void expensesQuery.refetch() })) : items.length === 0 ? (filtersActive ? (_jsx(EmptyState, { icon: SearchX, title: "\u041D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043D\u0430\u0448\u043B\u043E\u0441\u044C", description: "\u041F\u043E\u043F\u0440\u043E\u0431\u0443\u0439\u0442\u0435 \u0438\u0437\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u0435\u0440\u0438\u043E\u0434, \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044E \u0438\u043B\u0438 \u043F\u043E\u0438\u0441\u043A\u043E\u0432\u044B\u0439 \u0437\u0430\u043F\u0440\u043E\u0441.", action: _jsx(Button, { variant: "outline", onClick: clearFilters, children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0444\u0438\u043B\u044C\u0442\u0440\u044B" }) })) : (_jsx(EmptyState, { icon: Receipt, title: "\u0420\u0430\u0441\u0445\u043E\u0434\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442", description: "\u0414\u043E\u0431\u0430\u0432\u044C\u0442\u0435 \u043F\u0435\u0440\u0432\u044B\u0439 \u2014 \u0431\u0430\u043B\u0430\u043D\u0441\u044B \u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A\u043E\u0432 \u043E\u0431\u043D\u043E\u0432\u044F\u0442\u0441\u044F \u0441\u0440\u0430\u0437\u0443." }))) : (_jsxs("div", { className: "rounded-card bg-card px-3 pb-[22px] pt-3 shadow-card sm:px-7", children: [days.map((day, index) => (_jsxs("section", { children: [_jsxs("div", { className: cn("flex items-center justify-between gap-3 py-2 pt-4", index > 0 && "mt-2 border-t border-border/60 pt-5"), children: [_jsx("h3", { className: "text-[13px] font-bold uppercase tracking-[0.08em] text-dim", children: formatDayHeading(day.date) }), _jsx("span", { className: "text-sm font-semibold text-dim tabular-nums-money", children: formatMoney(day.totalCents, day.currency) })] }), _jsx("ul", { children: day.items.map((expense) => (_jsx("li", { children: _jsx(ExpenseCard, { expense: expense, currentUserId: currentUserId, onSelect: (selected) => setSelectedId(selected.id) }) }, expense.id))) })] }, `${day.key}-${index}`))), total > PAGE_SIZE ? (_jsxs("div", { className: "mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-1 pb-1 pt-5 sm:px-4", children: [_jsxs("p", { className: "text-sm text-dim", children: ["\u041F\u043E\u043A\u0430\u0437\u0430\u043D\u044B ", firstShown, "\u2013", lastShown, " \u0438\u0437 ", total] }), _jsxs("div", { className: "flex gap-2", children: [_jsxs(Button, { variant: "muted", size: "sm", className: "disabled:bg-subtle disabled:text-faint disabled:opacity-100 hover:bg-accent hover:text-accent-foreground [&_svg]:size-[15px]", disabled: page === 0, onClick: () => setPage((current) => Math.max(0, current - 1)), children: [_jsx(ChevronLeft, { strokeWidth: 2.2, "aria-hidden": "true" }), "\u041D\u0430\u0437\u0430\u0434"] }), _jsxs(Button, { variant: "muted", size: "sm", className: "disabled:bg-subtle disabled:text-faint disabled:opacity-100 hover:bg-accent hover:text-accent-foreground [&_svg]:size-[15px]", disabled: lastShown >= total, onClick: () => setPage((current) => current + 1), children: ["\u0414\u0430\u043B\u044C\u0448\u0435", _jsx(ChevronRight, { strokeWidth: 2.2, "aria-hidden": "true" })] })] })] })) : null] })), _jsx(ExpenseDetailDialog, { expenseId: selectedId, groupId: groupId, open: Boolean(selectedId), onOpenChange: (next) => {
                    if (!next)
                        setSelectedId(undefined);
                } })] }));
}
/** Подпись капсулы: «Период», пока диапазон пуст, иначе — сам диапазон. */
function periodLabel(dateFrom, dateTo) {
    if (dateFrom && dateTo)
        return `${formatDateShort(dateFrom)} — ${formatDateShort(dateTo)}`;
    if (dateFrom)
        return `с ${formatDateShort(dateFrom)}`;
    if (dateTo)
        return `по ${formatDateShort(dateTo)}`;
    return "Период";
}
/**
 * Период — такая же капсула, как остальные фильтры: пока он не задан, это одно
 * слово с шевроном, а два поля дат живут в поповере. Два видимых `input[date]`
 * в строке фильтров занимали втрое больше места и в пустом виде читались как
 * «дд.мм.гггг — дд.мм.гггг».
 */
function PeriodCapsule({ dateFrom, dateTo, onDateFromChange, onDateToChange, }) {
    const active = Boolean(dateFrom) || Boolean(dateTo);
    return (_jsxs("div", { className: cn("inline-flex h-[46px] shrink-0 snap-start items-center rounded-full transition-colors", active ? "bg-accent text-accent-foreground" : "bg-card text-muted-foreground shadow-flat"), children: [_jsxs(Popover, { children: [_jsxs(PopoverTrigger, { className: cn("inline-flex h-[46px] items-center gap-[9px] rounded-full px-[18px] text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", active
                            ? "pr-2 font-semibold text-accent-foreground"
                            : "font-medium text-muted-foreground hover:text-foreground"), "aria-label": active ? `Период: ${periodLabel(dateFrom, dateTo)}` : "Фильтр по периоду", children: [_jsx(CalendarRange, { className: cn("size-4 shrink-0", active ? "text-accent-foreground" : "text-dim"), "aria-hidden": "true" }), _jsx("span", { className: active ? "tabular-nums-money" : undefined, children: periodLabel(dateFrom, dateTo) }), active ? null : (_jsx(ChevronDown, { className: "size-[15px] shrink-0 text-dim", strokeWidth: 2.2, "aria-hidden": "true" }))] }), _jsx(PopoverContent, { align: "start", className: "w-[264px] rounded-field p-4", children: _jsxs("div", { className: "flex flex-col gap-3", children: [_jsxs("label", { className: "flex flex-col gap-1.5", children: [_jsx("span", { className: "text-[13px] font-semibold text-muted-foreground", children: "\u0421 \u0434\u0430\u0442\u044B" }), _jsx("input", { type: "date", value: dateFrom, max: dateTo || undefined, onChange: (event) => onDateFromChange(event.target.value), className: "h-11 w-full rounded-field border-0 bg-subtle px-3.5 text-[15px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring tabular-nums-money" })] }), _jsxs("label", { className: "flex flex-col gap-1.5", children: [_jsx("span", { className: "text-[13px] font-semibold text-muted-foreground", children: "\u041F\u043E \u0434\u0430\u0442\u0443" }), _jsx("input", { type: "date", value: dateTo, min: dateFrom || undefined, onChange: (event) => onDateToChange(event.target.value), className: "h-11 w-full rounded-field border-0 bg-subtle px-3.5 text-[15px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring tabular-nums-money" })] })] }) })] }), active ? (_jsx("button", { type: "button", onClick: () => {
                    onDateFromChange("");
                    onDateToChange("");
                }, "aria-label": "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u043F\u0435\u0440\u0438\u043E\u0434", className: "mr-[14px] flex size-5 shrink-0 items-center justify-center rounded-full text-accent-foreground/70 transition-colors hover:text-accent-foreground", children: _jsx(X, { className: "size-[15px]", strokeWidth: 2.4, "aria-hidden": "true" }) })) : null] }));
}
/**
 * Один фильтр-капсула. Выбранное значение красится в зелёную плашку и получает
 * крестик, пустое — остаётся белой капсулой с шевроном. Крестик живёт рядом с
 * триггером, а не внутри него: кнопка внутри кнопки — сломанная семантика.
 */
function FilterCapsule({ value, onValueChange, label, clearLabel, children, }) {
    const active = value !== ANY;
    return (_jsxs("div", { className: cn("inline-flex h-[46px] shrink-0 snap-start items-center rounded-full transition-colors", active
            ? "bg-accent text-accent-foreground hover:bg-accent-hover"
            : "bg-card text-muted-foreground shadow-flat"), children: [_jsxs(Select, { value: value, onValueChange: onValueChange, children: [_jsx(SelectTrigger, { "aria-label": label, className: cn("h-[46px] w-auto gap-[9px] rounded-full bg-transparent px-[18px] text-[15px]", active
                            ? "pr-2 font-semibold text-accent-foreground [&>svg]:hidden"
                            : "font-medium text-muted-foreground"), children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: children })] }), active ? (_jsx("button", { type: "button", onClick: () => onValueChange(ANY), "aria-label": clearLabel, className: "mr-[14px] flex size-5 shrink-0 items-center justify-center rounded-full text-accent-foreground/70 transition-colors hover:text-accent-foreground", children: _jsx(X, { className: "size-[15px]", strokeWidth: 2.4, "aria-hidden": "true" }) })) : null] }));
}
