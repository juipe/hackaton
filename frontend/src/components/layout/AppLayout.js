import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Plus } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";
import { AddExpenseDialog } from "@/components/expenses/AddExpenseDialog";
import { VoiceExpenseDialog } from "@/components/expenses/VoiceExpenseDialog";
import { AddExpenseContext, } from "@/components/layout/AddExpenseContext";
import { MobileNav } from "@/components/layout/MobileNav";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { VoiceExpenseDialogContext, } from "@/components/layout/VoiceExpenseDialogContext";
export function AppLayout() {
    const [isAddOpen, setIsAddOpen] = useState(false);
    const [presetGroupId, setPresetGroupId] = useState(undefined);
    const [isVoiceOpen, setIsVoiceOpen] = useState(false);
    const openAddExpense = useCallback((groupId) => {
        setPresetGroupId(groupId);
        setIsAddOpen(true);
    }, []);
    const openVoiceExpense = useCallback(() => setIsVoiceOpen(true), []);
    const contextValue = useMemo(() => ({ openAddExpense }), [openAddExpense]);
    const voiceContextValue = useMemo(() => ({ openVoiceExpense }), [openVoiceExpense]);
    return (_jsx(AddExpenseContext.Provider, { value: contextValue, children: _jsx(VoiceExpenseDialogContext.Provider, { value: voiceContextValue, children: _jsxs("div", { className: "min-h-screen bg-app", children: [_jsx(Sidebar, {}), _jsx(TopBar, {}), _jsx("div", { className: "lg:pl-[272px]", children: _jsx("main", { className: "flex w-full flex-col gap-6 px-4 py-5 pb-40 lg:pb-12 lg:pl-3 lg:pr-10 lg:pt-8", children: _jsx(Outlet, {}) }) }), _jsx("button", { type: "button", "aria-label": "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434", onClick: () => openAddExpense(), className: "fixed bottom-20 right-4 z-40 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-green transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95 lg:hidden", children: _jsx(Plus, { className: "size-6", "aria-hidden": true }) }), _jsx(MobileNav, {}), _jsx(AddExpenseDialog, { open: isAddOpen, onOpenChange: setIsAddOpen, groupId: presetGroupId }), _jsx(VoiceExpenseDialog, { open: isVoiceOpen, onOpenChange: setIsVoiceOpen })] }) }) }));
}
