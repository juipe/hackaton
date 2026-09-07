import { createContext, useContext } from "react";

export interface ReceiptExpenseDialogContextValue {
  /** Opens the global receipt-upload dialog; it asks the user to pick a group first. */
  openReceiptExpense: () => void;
}

/**
 * Same shape as VoiceExpenseDialogContext: the dialog state lives in AppLayout,
 * but the sidebar needs to open it without importing the layout (which would cycle).
 */
export const ReceiptExpenseDialogContext =
  createContext<ReceiptExpenseDialogContextValue | null>(null);

export function useReceiptExpenseDialog(): ReceiptExpenseDialogContextValue {
  const context = useContext(ReceiptExpenseDialogContext);
  if (!context) {
    throw new Error("useReceiptExpenseDialog must be used inside <AppLayout>");
  }
  return context;
}
