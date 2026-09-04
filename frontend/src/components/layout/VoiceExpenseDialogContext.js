import { createContext, useContext } from "react";
/**
 * Same shape as AddExpenseContext: the dialog state lives in AppLayout, but the
 * sidebar needs to open it without importing the layout (which would cycle).
 */
export const VoiceExpenseDialogContext = createContext(null);
export function useVoiceExpenseDialog() {
    const context = useContext(VoiceExpenseDialogContext);
    if (!context) {
        throw new Error("useVoiceExpenseDialog must be used inside <AppLayout>");
    }
    return context;
}
