export interface VoiceExpenseDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /**
     * When omitted (e.g. opened from the global sidebar, which has no group
     * context), a group-selection step runs first — recording only starts once
     * a group is picked.
     */
    groupId?: string;
}
export declare function VoiceExpenseDialog({ open, onOpenChange, groupId }: VoiceExpenseDialogProps): import("react").JSX.Element;
