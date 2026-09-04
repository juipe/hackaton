import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { CalendarRange } from "lucide-react";
import { useId } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PERIODS } from "@/lib/constants";
import { toDateInputValue } from "@/lib/format";
import { cn } from "@/lib/utils";
/**
 * Подписи капсул короче полных названий периодов: пять кнопок должны уместиться
 * в одну строку рядом с заголовком. Полное название остаётся в `aria-label`,
 * поэтому скринридер по-прежнему слышит «Последние 3 месяца», а не «3 месяца».
 */
const SHORT_LABELS = {
    all: "Всё время",
    this_month: "Месяц",
    last_month: "Прошлый",
    last_3_months: "3 месяца",
    custom: "Свой период",
};
/** The custom range opens on the last month so the dashboard never sits empty. */
function defaultRange() {
    const to = new Date();
    const from = new Date();
    from.setMonth(from.getMonth() - 1);
    return { date_from: toDateInputValue(from), date_to: toDateInputValue(to) };
}
export function PeriodFilter({ value, onChange, }) {
    const fromId = useId();
    const toId = useId();
    const period = value.period ?? "all";
    function selectPeriod(next) {
        if (next === period)
            return;
        if (next === "custom") {
            const range = defaultRange();
            onChange({
                ...value,
                period: "custom",
                date_from: value.date_from || range.date_from,
                date_to: value.date_to || range.date_to,
            });
            return;
        }
        onChange({ ...value, period: next, date_from: undefined, date_to: undefined });
    }
    // Dragging one end past the other would ask the API for a negative range, so the
    // other end follows instead of producing an error the user cannot see coming.
    function setFrom(next) {
        const dateTo = value.date_to && next && next > value.date_to ? next : value.date_to;
        onChange({ ...value, period: "custom", date_from: next, date_to: dateTo });
    }
    function setTo(next) {
        const dateFrom = value.date_from && next && next < value.date_from ? next : value.date_from;
        onChange({ ...value, period: "custom", date_from: dateFrom, date_to: next });
    }
    return (_jsxs("div", { className: "w-full min-w-0 space-y-3 lg:w-auto", children: [_jsx("div", { className: "no-scrollbar -mx-1 snap-x snap-proximity overflow-x-auto scroll-px-1 px-1 py-1", children: _jsx("div", { role: "group", "aria-label": "\u041F\u0435\u0440\u0438\u043E\u0434 \u0441\u0432\u043E\u0434\u043A\u0438", className: "inline-flex w-max items-center gap-1 rounded-full bg-card p-[5px] shadow-flat", children: PERIODS.map((option) => {
                        const active = option.value === period;
                        return (_jsxs("button", { type: "button", "aria-pressed": active, "aria-label": option.label, onClick: () => selectPeriod(option.value), className: cn("inline-flex h-11 snap-start items-center gap-1.5 whitespace-nowrap rounded-full px-[18px] text-sm transition-colors", active
                                ? "bg-primary font-bold text-primary-foreground"
                                : "font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"), children: [option.value === "custom" ? (_jsx(CalendarRange, { className: "size-4", "aria-hidden": true })) : null, SHORT_LABELS[option.value]] }, option.value));
                    }) }) }), period === "custom" ? (_jsxs("div", { className: "flex flex-wrap items-end gap-3", children: [_jsxs("div", { className: "min-w-0 flex-1 sm:flex-none", children: [_jsx(Label, { htmlFor: fromId, children: "\u041D\u0430\u0447\u0430\u043B\u043E" }), _jsx(Input, { id: fromId, type: "date", value: value.date_from ?? "", onChange: (event) => setFrom(event.target.value), className: "mt-2 sm:w-44" })] }), _jsxs("div", { className: "min-w-0 flex-1 sm:flex-none", children: [_jsx(Label, { htmlFor: toId, children: "\u041A\u043E\u043D\u0435\u0446" }), _jsx(Input, { id: toId, type: "date", value: value.date_to ?? "", onChange: (event) => setTo(event.target.value), className: "mt-2 sm:w-44" })] })] })) : null] }));
}
