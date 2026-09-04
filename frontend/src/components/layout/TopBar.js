import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { UserMenu } from "@/components/layout/UserMenu";
import { Wordmark } from "@/components/layout/Wordmark";
/** Только для экранов уже `lg`: на десктопе всё живёт в сайдбаре. */
export function TopBar() {
    return (_jsxs("header", { className: "sticky top-0 z-30 flex h-14 items-center justify-between gap-3 bg-app/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-app/90 lg:hidden", children: [_jsx(Wordmark, { size: "sm" }), _jsx(UserMenu, {})] }));
}
