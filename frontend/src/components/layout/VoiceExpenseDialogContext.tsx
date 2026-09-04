import { createContext, useContext } from "react";

export interface VoiceExpenseDialogContextValue {
  /** Opens the global voice-expense dialog; it asks the user to pick a group first. */
  openVoiceExpense: () => void;
}

/**
 * Same shape as AddExpenseContext: the dialog state lives in AppLayout, but the
 * sidebar needs to open it without importing the layout (which would cycle).
 */
export const VoiceExpenseDialogContext = createContext<VoiceExpenseDialogContextValue | null>(
  null,
);

export function useVoiceExpenseDialog(): VoiceExpenseDialogContextValue {
  const context = useContext(VoiceExpenseDialogContext);
  if (!context) {
    throw new Error("useVoiceExpenseDialog must be used inside <AppLayout>");
  }
  return context;
}
