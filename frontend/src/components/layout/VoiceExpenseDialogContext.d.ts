export interface VoiceExpenseDialogContextValue {
    /** Opens the global voice-expense dialog; it asks the user to pick a group first. */
    openVoiceExpense: () => void;
}
/**
 * Same shape as AddExpenseContext: the dialog state lives in AppLayout, but the
 * sidebar needs to open it without importing the layout (which would cycle).
 */
export declare const VoiceExpenseDialogContext: import("react").Context<VoiceExpenseDialogContextValue | null>;
export declare function useVoiceExpenseDialog(): VoiceExpenseDialogContextValue;
