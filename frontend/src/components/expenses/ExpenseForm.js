import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { AlertCircle, FileText, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { CategoryIcon } from "@/components/common/CategoryIcon";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { UserAvatar } from "@/components/common/UserAvatar";
import { ParticipantSelector } from "@/components/expenses/ParticipantSelector";
import { SplitEditor } from "@/components/expenses/SplitEditor";
import { buildParticipantValues, computeSplitPreview, seedSplitRows, } from "@/components/expenses/splitMath";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCategories } from "@/hooks/useCategories";
import { useCreateExpense, useUpdateExpense } from "@/hooks/useExpenses";
import { useAuth } from "@/hooks/useAuth";
import { useGroup, useMembers } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { SPLIT_MODES } from "@/lib/constants";
import { dateInputToIso, todayInputValue, toDateInputValue } from "@/lib/format";
import { centsToInput, currencySymbol, parseAmountToCents } from "@/lib/money";
import { cn } from "@/lib/utils";
/** Надзаголовок из §2.5 контракта: 13px / 700 / uppercase / трекинг 0.08em. */
const OVERLINE = "text-[13px] font-bold uppercase tracking-[0.08em] text-dim";
/** `input_value` for an exact split is whole cents; the input shows major units. */
function rowsFromExpense(expense) {
    const rows = {};
    for (const split of expense.splits) {
        if (expense.split_mode === "equal") {
            rows[split.user_id] = "";
        }
        else if (expense.split_mode === "exact") {
            rows[split.user_id] = centsToInput(Math.round(Number(split.input_value ?? 0)));
        }
        else {
            // The API serialises percentages and shares with a dot; the field shows a comma.
            rows[split.user_id] = (split.input_value ?? "").replace(".", ",");
        }
    }
    return rows;
}
export function ExpenseForm({ groupId, expense, voiceDraft, onDone, onCancel, }) {
    const { user } = useAuth();
    const membersQuery = useMembers(groupId);
    const categoriesQuery = useCategories();
    const groupQuery = useGroup(groupId);
    const createExpense = useCreateExpense(groupId);
    const updateExpense = useUpdateExpense(expense?.id ?? "", groupId);
    const [draft, setDraft] = useState(null);
    const [attempted, setAttempted] = useState(false);
    const [showNote, setShowNote] = useState(Boolean(expense?.description) || Boolean(voiceDraft?.description));
    const amountRef = useRef(null);
    const members = membersQuery.data;
    const categories = categoriesQuery.data;
    const group = groupQuery.data;
    const currentUserId = user?.id;
    useEffect(() => {
        if (draft || !members || !categories || !group)
            return;
        if (expense) {
            setDraft({
                amountText: centsToInput(expense.amount_cents),
                title: expense.title,
                description: expense.description ?? "",
                categoryId: expense.category.id,
                dateValue: toDateInputValue(expense.occurred_at),
                payerId: expense.paid_by,
                participantIds: expense.splits.map((split) => split.user_id),
                mode: expense.split_mode,
                rows: rowsFromExpense(expense),
            });
            return;
        }
        if (voiceDraft) {
            const payerId = voiceDraft.payer.status === "resolved" && voiceDraft.payer.value
                ? voiceDraft.payer.value.user.id
                : "";
            const categoryId = voiceDraft.category.status === "resolved" && voiceDraft.category.value
                ? voiceDraft.category.value.id
                : "";
            const resolvedParticipantIds = voiceDraft.participants.resolved.map((participant) => participant.member.user.id);
            const participantIds = payerId && !resolvedParticipantIds.includes(payerId)
                ? [...resolvedParticipantIds, payerId]
                : resolvedParticipantIds;
            // The row inputs are edited as human-typed decimals with a comma, same
            // as `rowsFromExpense` below — the API (and this draft) use a dot.
            const rows = voiceDraft.split_mode === "equal"
                ? {}
                : Object.fromEntries(voiceDraft.participants.resolved.map((participant) => [
                    participant.member.user.id,
                    (participant.value ?? "").replace(".", ","),
                ]));
            setDraft({
                amountText: voiceDraft.amount_cents !== null ? centsToInput(voiceDraft.amount_cents) : "",
                title: voiceDraft.title ?? "",
                description: voiceDraft.description ?? "",
                categoryId,
                dateValue: voiceDraft.occurred_at ? toDateInputValue(voiceDraft.occurred_at) : todayInputValue(),
                payerId,
                participantIds,
                mode: voiceDraft.split_mode,
                rows,
            });
            return;
        }
        const memberIds = members.map((member) => member.user.id);
        const payerId = currentUserId && memberIds.includes(currentUserId)
            ? currentUserId
            : (memberIds[0] ?? "");
        // "Other" is the neutral default, so adding an expense never forces a
        // category decision the user has not made yet.
        const category = categories.find((item) => item.slug === "other") ?? categories[0];
        setDraft({
            amountText: "",
            title: "",
            description: "",
            categoryId: category?.id ?? "",
            dateValue: todayInputValue(),
            payerId,
            participantIds: memberIds,
            mode: "equal",
            rows: {},
        });
    }, [draft, members, categories, group, expense, voiceDraft, currentUserId]);
    const isReady = draft !== null;
    useEffect(() => {
        if (!isReady)
            return;
        const frame = window.requestAnimationFrame(() => amountRef.current?.focus());
        return () => window.cancelAnimationFrame(frame);
    }, [isReady]);
    const amountCents = draft ? (parseAmountToCents(draft.amountText) ?? 0) : 0;
    const mode = draft?.mode ?? "equal";
    const participantIds = useMemo(() => draft?.participantIds ?? [], [draft?.participantIds]);
    const rows = useMemo(() => draft?.rows ?? {}, [draft?.rows]);
    const preview = useMemo(() => computeSplitPreview({ mode, amountCents, participantIds, rows }), [mode, amountCents, participantIds, rows]);
    const formError = (() => {
        if (!draft)
            return null;
        if (amountCents <= 0)
            return "Сумма должна быть больше нуля";
        if (!draft.title.trim())
            return "Укажите название";
        if (!draft.categoryId)
            return "Выберите категорию";
        if (participantIds.length === 0)
            return "Добавьте хотя бы одного участника";
        if (!participantIds.includes(draft.payerId)) {
            return "Плательщик должен быть среди участников";
        }
        return preview.error;
    })();
    const update = (patch) => {
        setDraft((current) => (current ? { ...current, ...patch } : current));
    };
    const changeMode = (next) => {
        setDraft((current) => current
            ? {
                ...current,
                mode: next,
                rows: seedSplitRows(next, current.participantIds, parseAmountToCents(current.amountText) ?? 0),
            }
            : current);
    };
    const changeParticipants = (ids) => {
        setDraft((current) => {
            if (!current)
                return current;
            const amount = parseAmountToCents(current.amountText) ?? 0;
            // Percentages describe a specific group of people, so changing who is in
            // it invalidates them — reseeding keeps the form submittable.
            if (current.mode === "percentage") {
                return {
                    ...current,
                    participantIds: ids,
                    rows: seedSplitRows("percentage", ids, amount),
                };
            }
            const next = {};
            for (const id of ids) {
                const existing = current.rows[id];
                if (existing !== undefined && existing !== "")
                    next[id] = existing;
                else if (current.mode === "shares")
                    next[id] = "1";
                else
                    next[id] = "";
            }
            return { ...current, participantIds: ids, rows: next };
        });
    };
    const changePayer = (payerId) => {
        setDraft((current) => {
            if (!current)
                return current;
            if (current.participantIds.includes(payerId))
                return { ...current, payerId };
            const memberIds = (members ?? []).map((member) => member.user.id);
            const participants = memberIds.filter((id) => current.participantIds.includes(id) || id === payerId);
            const amount = parseAmountToCents(current.amountText) ?? 0;
            return {
                ...current,
                payerId,
                participantIds: participants,
                rows: current.mode === "percentage"
                    ? seedSplitRows("percentage", participants, amount)
                    : { ...current.rows, [payerId]: current.mode === "shares" ? "1" : "" },
            };
        });
    };
    const isSaving = createExpense.isPending || updateExpense.isPending;
    async function handleSubmit(event) {
        event.preventDefault();
        setAttempted(true);
        if (!draft || formError || isSaving)
            return;
        const input = {
            title: draft.title.trim(),
            description: draft.description.trim() || null,
            amount_cents: amountCents,
            category_id: draft.categoryId,
            paid_by: draft.payerId,
            occurred_at: dateInputToIso(draft.dateValue),
            split_mode: draft.mode,
            participants: buildParticipantValues({
                mode: draft.mode,
                participantIds,
                rows: draft.rows,
                amounts: preview.amounts,
            }),
        };
        try {
            if (expense) {
                await updateExpense.mutateAsync(input);
                toast.success("Расход изменён");
            }
            else {
                await createExpense.mutateAsync(input);
                toast.success(`Расход «${input.title}» добавлен`);
            }
            onDone?.();
        }
        catch (error) {
            toast.error(errorMessage(error));
        }
    }
    if (membersQuery.isError || categoriesQuery.isError || groupQuery.isError) {
        return (_jsx(ErrorState, { error: membersQuery.error ?? categoriesQuery.error ?? groupQuery.error, onRetry: () => {
                void membersQuery.refetch();
                void categoriesQuery.refetch();
                void groupQuery.refetch();
            } }));
    }
    if (!draft || !members || !categories || !group) {
        return _jsx(LoadingState, { label: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u0433\u0440\u0443\u043F\u043F\u0443\u2026" });
    }
    const currency = group.currency;
    const symbol = currencySymbol(currency);
    const activeMode = SPLIT_MODES.find((item) => item.value === draft.mode);
    const activeCategory = categories.find((item) => item.id === draft.categoryId);
    const payer = members.find((member) => member.user.id === draft.payerId)?.user;
    const showErrors = attempted || amountCents > 0;
    return (_jsxs("form", { onSubmit: handleSubmit, className: "flex flex-col", noValidate: true, children: [_jsxs("div", { className: "mt-2.5 rounded-[22px] bg-subtle px-5 py-5 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-card sm:px-6 sm:py-[22px]", children: [_jsx(Label, { htmlFor: "expense-amount", className: OVERLINE, children: "\u0421\u0443\u043C\u043C\u0430" }), _jsxs("div", { className: "mt-2 flex items-baseline gap-2", children: [_jsx(Input, { id: "expense-amount", ref: amountRef, type: "text", value: draft.amountText, onChange: (event) => update({ amountText: event.target.value.replace(/[^\d.,]/g, "") }), inputMode: "decimal", autoComplete: "off", placeholder: "0,00", className: "h-auto min-w-0 flex-1 rounded-none bg-transparent p-0 text-[36px] font-bold leading-none tracking-[-0.035em] tabular-nums-money focus-visible:ring-0 focus-visible:ring-offset-0 sm:text-[44px]" }), _jsx("span", { "aria-hidden": "true", className: "shrink-0 text-[24px] font-semibold leading-none text-dim sm:text-[30px]", children: symbol })] })] }), _jsxs("div", { className: "mt-5 flex flex-col gap-[18px]", children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "expense-title", children: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435" }), _jsx(Input, { id: "expense-title", value: draft.title, onChange: (event) => update({ title: event.target.value }), maxLength: 160, placeholder: "\u041F\u0440\u043E\u0434\u0443\u043A\u0442\u044B \u043D\u0430 \u043D\u0435\u0434\u0435\u043B\u044E", autoComplete: "off" })] }), _jsxs("div", { className: "grid gap-3.5 sm:grid-cols-2", children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "expense-category", children: "\u041A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F" }), _jsxs(Select, { value: draft.categoryId, onValueChange: (value) => update({ categoryId: value }), children: [_jsx(SelectTrigger, { id: "expense-category", className: "[&>span]:line-clamp-none [&>span]:min-w-0 [&>span]:flex-1", children: _jsx(SelectValue, { placeholder: "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044E", children: activeCategory ? (_jsxs("span", { className: "flex min-w-0 items-center gap-2.5", children: [_jsx(CategoryIcon, { name: activeCategory.icon, className: "size-[18px] shrink-0 text-muted-foreground" }), _jsx("span", { className: "truncate", children: activeCategory.name })] })) : null }) }), _jsx(SelectContent, { children: categories.map((category) => (_jsx(SelectItem, { value: category.id, children: _jsxs("span", { className: "flex items-center gap-2.5", children: [_jsx(CategoryIcon, { name: category.icon, className: "size-[18px] text-muted-foreground" }), category.name] }) }, category.id))) })] })] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "expense-date", children: "\u0414\u0430\u0442\u0430" }), _jsx(Input, { id: "expense-date", type: "date", value: draft.dateValue, onChange: (event) => update({ dateValue: event.target.value }), className: "tabular-nums-money" })] })] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "expense-payer", children: "\u041A\u0442\u043E \u0437\u0430\u043F\u043B\u0430\u0442\u0438\u043B" }), _jsxs(Select, { value: draft.payerId, onValueChange: changePayer, children: [_jsx(SelectTrigger, { id: "expense-payer", className: "py-0 pl-2.5 pr-[14px] [&>span]:line-clamp-none [&>span]:min-w-0 [&>span]:flex-1", children: _jsx(SelectValue, { placeholder: "\u041A\u0442\u043E \u0437\u0430\u043F\u043B\u0430\u0442\u0438\u043B?", children: payer ? (_jsxs("span", { className: "flex min-w-0 items-center gap-2.5", children: [_jsx(UserAvatar, { user: payer, size: "sm" }), _jsx("span", { className: "truncate", children: payer.id === currentUserId ? `${payer.name} (вы)` : payer.name })] })) : null }) }), _jsx(SelectContent, { children: members.map((member) => (_jsx(SelectItem, { value: member.user.id, children: member.user.id === currentUserId
                                                ? `${member.user.name} (вы)`
                                                : member.user.name }, member.id))) })] })] }), _jsxs("div", { className: "space-y-2.5", children: [_jsx(Label, { children: "\u041C\u0435\u0436\u0434\u0443 \u043A\u0435\u043C \u0434\u0435\u043B\u0438\u043C" }), _jsx(ParticipantSelector, { members: members, selectedIds: draft.participantIds, onChange: changeParticipants, payerId: draft.payerId })] }), _jsxs("div", { className: "space-y-2.5", children: [_jsx(Label, { children: "\u041A\u0430\u043A \u0434\u0435\u043B\u0438\u043C" }), _jsx("div", { role: "group", "aria-label": "\u041A\u0430\u043A \u0434\u0435\u043B\u0438\u043C", className: "grid grid-cols-2 gap-1 rounded-[24px] bg-subtle p-[5px] sm:flex sm:items-center sm:rounded-full", children: SPLIT_MODES.map((item) => {
                                    const active = item.value === draft.mode;
                                    return (_jsx("button", { type: "button", "aria-pressed": active, onClick: () => changeMode(item.value), className: cn("h-10 min-w-0 rounded-full px-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:flex-1", active
                                            ? "bg-primary font-bold text-primary-foreground"
                                            : "font-medium text-muted-foreground hover:bg-card hover:text-foreground"), children: item.label }, item.value));
                                }) }), activeMode ? _jsx("p", { className: "text-[13px] text-dim", children: activeMode.hint }) : null] }), _jsx(SplitEditor, { mode: draft.mode, amountCents: amountCents, currency: currency, members: members, participantIds: draft.participantIds, rows: draft.rows, onRowsChange: (next) => update({ rows: next }), payerId: draft.payerId }), showNote ? (_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "expense-note", children: "\u0417\u0430\u043C\u0435\u0442\u043A\u0430" }), _jsx(Textarea, { id: "expense-note", value: draft.description, onChange: (event) => update({ description: event.target.value }), placeholder: "\u0427\u0442\u043E \u0432\u0430\u0436\u043D\u043E \u043F\u043E\u043C\u043D\u0438\u0442\u044C \u043E\u0431 \u044D\u0442\u043E\u043C \u0440\u0430\u0441\u0445\u043E\u0434\u0435", rows: 3 })] })) : (_jsxs(Button, { variant: "ghost", size: "sm", className: "h-auto self-start px-0 py-2 text-sm font-semibold text-dim hover:bg-transparent hover:text-accent-foreground [&_svg]:size-4", onClick: () => setShowNote(true), children: [_jsx(FileText, { "aria-hidden": "true" }), "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0437\u0430\u043C\u0435\u0442\u043A\u0443"] })), showErrors && formError ? (_jsxs("p", { className: "flex items-start gap-2 text-sm text-negative", role: "alert", children: [_jsx(AlertCircle, { className: "mt-0.5 size-4 shrink-0", "aria-hidden": "true" }), _jsx("span", { children: formError })] })) : null] }), _jsxs("div", { className: "mt-[26px] flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-2.5", children: [onCancel ? (_jsx(Button, { variant: "secondary", size: "lg", onClick: onCancel, disabled: isSaving, className: "w-full sm:w-auto", children: "\u041E\u0442\u043C\u0435\u043D\u0430" })) : null, _jsxs(Button, { type: "submit", size: "lg", disabled: isSaving, className: "w-full sm:w-auto", children: [isSaving ? _jsx(Loader2, { className: "animate-spin", "aria-hidden": "true" }) : null, expense ? "Сохранить" : "Добавить расход"] })] })] }));
}
