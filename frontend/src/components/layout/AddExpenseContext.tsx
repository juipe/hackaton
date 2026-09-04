import { createContext, useContext } from "react";

import type { Uuid } from "@/types/api";

export interface AddExpenseContextValue {
  /** Opens the global Add expense dialog, optionally pre-selecting a group. */
  openAddExpense: (groupId?: Uuid) => void;
}

/**
 * The dialog state lives in AppLayout, but the sidebar, the bottom bar and the FAB
 * all need to open it. A context keeps those components prop-free (and keeps the
 * layout out of an import cycle with them).
 */
export const AddExpenseContext = createContext<AddExpenseContextValue | null>(null);

export function useAddExpense(): AddExpenseContextValue {
  const context = useContext(AddExpenseContext);
  if (!context) {
    throw new Error("useAddExpense must be used inside <AppLayout>");
  }
  return context;
}
