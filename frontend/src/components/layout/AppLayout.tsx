import { Plus } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";

import { AddExpenseDialog } from "@/components/expenses/AddExpenseDialog";
import { VoiceExpenseDialog } from "@/components/expenses/VoiceExpenseDialog";
import {
  AddExpenseContext,
  type AddExpenseContextValue,
} from "@/components/layout/AddExpenseContext";
import { MobileNav } from "@/components/layout/MobileNav";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import {
  VoiceExpenseDialogContext,
  type VoiceExpenseDialogContextValue,
} from "@/components/layout/VoiceExpenseDialogContext";
import type { Uuid } from "@/types/api";

export function AppLayout() {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [presetGroupId, setPresetGroupId] = useState<Uuid | undefined>(undefined);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);

  const openAddExpense = useCallback((groupId?: Uuid) => {
    setPresetGroupId(groupId);
    setIsAddOpen(true);
  }, []);

  const openVoiceExpense = useCallback(() => setIsVoiceOpen(true), []);

  const contextValue = useMemo<AddExpenseContextValue>(
    () => ({ openAddExpense }),
    [openAddExpense],
  );
  const voiceContextValue = useMemo<VoiceExpenseDialogContextValue>(
    () => ({ openVoiceExpense }),
    [openVoiceExpense],
  );

  return (
    <AddExpenseContext.Provider value={contextValue}>
      <VoiceExpenseDialogContext.Provider value={voiceContextValue}>
        <div className="min-h-screen bg-app">
          <Sidebar />
          <TopBar />

          <div className="lg:pl-[272px]">
            {/* Ширину не ограничиваем: макет 1440 без ограничителя, контент тянется. */}
            {/* pb-40 clears the fixed FAB (bottom-20 + size-14 ≈ 136px) with headroom to spare. */}
            <main className="flex w-full flex-col gap-6 px-4 py-5 pb-40 lg:pb-12 lg:pl-3 lg:pr-10 lg:pt-8">
              <Outlet />
            </main>
          </div>

          <button
            type="button"
            aria-label="Добавить расход"
            onClick={() => openAddExpense()}
            className="fixed bottom-20 right-4 z-40 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-green transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95 lg:hidden"
          >
            <Plus className="size-6" aria-hidden />
          </button>

          <MobileNav />

          <AddExpenseDialog
            open={isAddOpen}
            onOpenChange={setIsAddOpen}
            groupId={presetGroupId}
          />
          <VoiceExpenseDialog open={isVoiceOpen} onOpenChange={setIsVoiceOpen} />
        </div>
      </VoiceExpenseDialogContext.Provider>
    </AddExpenseContext.Provider>
  );
}
