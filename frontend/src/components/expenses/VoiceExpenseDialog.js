import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { AlertTriangle, ChevronRight, Loader2, Mic, MicOff, Quote, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ErrorState } from "@/components/common/ErrorState";
import { GroupAvatar } from "@/components/common/GroupAvatar";
import { LoadingState } from "@/components/common/LoadingState";
import { ExpenseForm } from "@/components/expenses/ExpenseForm";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, } from "@/components/ui/dialog";
import { useGroups } from "@/hooks/useGroups";
import { useCreateVoiceExpenseDraft } from "@/hooks/useVoiceExpense";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
/** Preference order — the browser picks the first it actually supports. */
const CANDIDATE_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
];
function pickMimeType() {
    if (typeof MediaRecorder === "undefined")
        return undefined;
    return CANDIDATE_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}
function isRecordingSupported() {
    return (typeof window !== "undefined" &&
        typeof MediaRecorder !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia));
}
function formatElapsed(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
}
function stopStream(stream) {
    stream?.getTracks().forEach((track) => track.stop());
}
export function VoiceExpenseDialog({ open, onOpenChange, groupId }) {
    const [pickedGroupId, setPickedGroupId] = useState(undefined);
    const [stage, setStage] = useState("idle");
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [errorText, setErrorText] = useState(null);
    const [draft, setDraft] = useState(null);
    const streamRef = useRef(null);
    const recorderRef = useRef(null);
    const chunksRef = useRef([]);
    const timerRef = useRef(null);
    const activeGroupId = groupId ?? pickedGroupId;
    const showGroupPicker = !activeGroupId;
    const groupsQuery = useGroups();
    const createDraft = useCreateVoiceExpenseDraft(activeGroupId ?? "");
    const supported = isRecordingSupported();
    const reset = () => {
        if (timerRef.current !== null) {
            window.clearInterval(timerRef.current);
            timerRef.current = null;
        }
        stopStream(streamRef.current);
        streamRef.current = null;
        recorderRef.current = null;
        chunksRef.current = [];
        setElapsedSeconds(0);
        setErrorText(null);
        setDraft(null);
        setStage("idle");
        // A fixed groupId (group-page mic) never needs re-picking; the sidebar
        // mic starts over at the group step every time it's reopened.
        if (!groupId)
            setPickedGroupId(undefined);
    };
    // Recording must not keep running (or the mic light stay on) once the
    // dialog is closed some other way — the close button, Esc, outside click.
    useEffect(() => {
        if (!open)
            reset();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);
    useEffect(() => () => reset(), []);
    async function handleUpload(blob) {
        setStage("processing");
        try {
            const result = await createDraft.mutateAsync(blob);
            setDraft(result);
            setStage("review");
        }
        catch (error) {
            setErrorText(errorMessage(error));
            setStage("error");
        }
    }
    async function startRecording() {
        setErrorText(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;
            const mimeType = pickMimeType();
            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
            chunksRef.current = [];
            recorder.ondataavailable = (event) => {
                if (event.data.size > 0)
                    chunksRef.current.push(event.data);
            };
            recorder.onstop = () => {
                stopStream(streamRef.current);
                streamRef.current = null;
                const blob = new Blob(chunksRef.current, { type: mimeType ?? "audio/webm" });
                void handleUpload(blob);
            };
            recorderRef.current = recorder;
            recorder.start();
            setElapsedSeconds(0);
            setStage("recording");
            timerRef.current = window.setInterval(() => {
                setElapsedSeconds((seconds) => seconds + 1);
            }, 1000);
        }
        catch {
            setErrorText("Не удалось получить доступ к микрофону. Проверьте разрешения браузера.");
            setStage("error");
        }
    }
    function stopRecording() {
        if (timerRef.current !== null) {
            window.clearInterval(timerRef.current);
            timerRef.current = null;
        }
        recorderRef.current?.stop();
    }
    function cancelRecording() {
        if (timerRef.current !== null) {
            window.clearInterval(timerRef.current);
            timerRef.current = null;
        }
        if (recorderRef.current) {
            recorderRef.current.onstop = null;
            recorderRef.current.stop();
        }
        stopStream(streamRef.current);
        streamRef.current = null;
        setElapsedSeconds(0);
        setStage("idle");
    }
    const title = showGroupPicker
        ? "Голосовой ввод"
        : stage === "review"
            ? "Проверьте расход"
            : stage === "error"
                ? "Не получилось"
                : "Голосовой ввод";
    return (_jsx(Dialog, { open: open, onOpenChange: onOpenChange, children: _jsxs(DialogContent, { className: stage === "review" || showGroupPicker ? undefined : "sm:max-w-[480px]", onOpenAutoFocus: (event) => {
                if (stage === "review" || showGroupPicker)
                    event.preventDefault();
            }, children: [_jsxs(DialogHeader, { className: "space-y-[5px]", children: [_jsx(DialogTitle, { children: title }), _jsxs(DialogDescription, { children: [showGroupPicker && "В какую группу добавить расход?", !showGroupPicker && stage === "idle" &&
                                    "Опишите расход голосом — распознаем сумму, категорию и участников.", !showGroupPicker && stage === "recording" &&
                                    "Говорите, потом нажмите на квадрат, чтобы остановить.", !showGroupPicker && stage === "processing" &&
                                    "Расшифровываем запись и извлекаем данные локально.", !showGroupPicker && stage === "review" &&
                                    "Проверьте, что мы распознали, и поправьте, что нужно.", !showGroupPicker && stage === "error" && "Можно попробовать ещё раз."] })] }), showGroupPicker ? (_jsx("div", { className: "flex flex-col gap-2", children: groupsQuery.isPending ? (_jsx(LoadingState, { label: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u0432\u0430\u0448\u0438 \u0433\u0440\u0443\u043F\u043F\u044B\u2026" })) : groupsQuery.isError ? (_jsx(ErrorState, { error: groupsQuery.error, onRetry: () => void groupsQuery.refetch() })) : groupsQuery.data.length === 0 ? (_jsx("p", { className: "px-1 py-4 text-[15px] text-muted-foreground", children: "\u0413\u0440\u0443\u043F\u043F \u043F\u043E\u043A\u0430 \u043D\u0435\u0442 \u2014 \u0441\u043E\u0437\u0434\u0430\u0439\u0442\u0435 \u0433\u0440\u0443\u043F\u043F\u0443, \u0447\u0442\u043E\u0431\u044B \u0434\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0430\u0441\u0445\u043E\u0434." })) : (groupsQuery.data.map((group) => (_jsxs("button", { type: "button", onClick: () => setPickedGroupId(group.id), className: "flex w-full items-center gap-3.5 rounded-row bg-subtle px-4 py-3.5 text-left transition-colors hover:bg-subtle-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", children: [_jsx(GroupAvatar, { group: group, size: "sm" }), _jsxs("span", { className: "min-w-0 flex-1", children: [_jsx("span", { className: "block truncate text-[15px] font-semibold text-foreground", children: group.name }), _jsx("span", { className: "block text-[13px] text-dim", children: plural(group.member_count, "участник", "участника", "участников") })] }), _jsx(ChevronRight, { className: "size-[18px] shrink-0 text-faint", "aria-hidden": "true" })] }, group.id)))) })) : null, !showGroupPicker && stage === "idle" ? (_jsxs("div", { className: "flex flex-col items-center justify-center gap-5 px-5 py-9 text-center sm:px-6 sm:py-10", children: [supported ? (_jsx("button", { type: "button", onClick: () => void startRecording(), "aria-label": "\u041D\u0430\u0447\u0430\u0442\u044C \u0437\u0430\u043F\u0438\u0441\u044C", className: "flex size-24 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-green transition-transform hover:bg-primary-hover active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", children: _jsx(Mic, { className: "size-9", "aria-hidden": "true" }) })) : (_jsx("span", { className: "flex size-24 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground", children: _jsx(MicOff, { className: "size-9", "aria-hidden": "true" }) })), _jsx("p", { className: "max-w-[36ch] text-[15px] text-muted-foreground", children: supported
                                ? "Нажмите на микрофон и назовите сумму, за что заплатили и с кем делите."
                                : "Браузер не поддерживает запись звука. Попробуйте другой браузер или введите расход вручную." })] })) : null, !showGroupPicker && stage === "recording" ? (_jsxs("div", { className: "flex flex-col items-center justify-center gap-5 px-5 py-9 text-center sm:px-6 sm:py-10", children: [_jsxs("div", { className: "relative flex size-24 shrink-0 items-center justify-center", children: [_jsx("span", { className: "absolute inset-0 animate-pulse rounded-full bg-destructive/20", "aria-hidden": "true" }), _jsx("button", { type: "button", onClick: stopRecording, "aria-label": "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u0437\u0430\u043F\u0438\u0441\u044C", className: "relative flex size-24 shrink-0 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-green transition-transform active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", children: _jsx(Square, { className: "size-8 fill-current", "aria-hidden": "true" }) })] }), _jsx("p", { className: "text-[28px] font-bold tabular-nums-money leading-none tracking-[-0.02em] text-foreground", "aria-live": "polite", children: formatElapsed(elapsedSeconds) }), _jsx(Button, { variant: "secondary", size: "sm", onClick: cancelRecording, children: "\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C" })] })) : null, !showGroupPicker && stage === "processing" ? (_jsxs("div", { className: "flex flex-col items-center justify-center gap-3 px-5 py-9 text-center sm:px-6 sm:py-10", children: [_jsx("span", { className: "flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground", children: _jsx(Loader2, { className: "size-6 animate-spin", "aria-hidden": "true" }) }), _jsx("p", { className: "text-[15px] font-semibold text-foreground", children: "\u0420\u0430\u0441\u043F\u043E\u0437\u043D\u0430\u0451\u043C \u0440\u0435\u0447\u044C \u0438 \u0434\u0430\u043D\u043D\u044B\u0435 \u043E \u0440\u0430\u0441\u0445\u043E\u0434\u0435\u2026" }), _jsx("p", { className: "max-w-[36ch] text-[13px] text-dim", children: "Whisper \u0438 Qwen \u0440\u0430\u0431\u043E\u0442\u0430\u044E\u0442 \u043B\u043E\u043A\u0430\u043B\u044C\u043D\u043E \u2014 \u044D\u0442\u043E \u043C\u043E\u0436\u0435\u0442 \u0437\u0430\u043D\u044F\u0442\u044C \u0434\u043E \u043F\u0430\u0440\u044B \u043C\u0438\u043D\u0443\u0442." })] })) : null, !showGroupPicker && stage === "error" ? (_jsxs("div", { className: "flex flex-col items-center justify-center gap-4 px-5 py-9 text-center sm:px-6 sm:py-10", children: [_jsx("span", { className: "flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-negative", children: _jsx(AlertTriangle, { className: "size-6", "aria-hidden": "true" }) }), _jsx("p", { className: "mx-auto max-w-[44ch] text-[15px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]", children: errorText }), _jsx(Button, { type: "button", size: "sm", onClick: reset, children: "\u041F\u043E\u043F\u0440\u043E\u0431\u043E\u0432\u0430\u0442\u044C \u0441\u043D\u043E\u0432\u0430" })] })) : null, !showGroupPicker && stage === "review" && draft && activeGroupId ? (_jsxs(_Fragment, { children: [_jsx(VoiceDraftSummary, { draft: draft }), _jsx(ExpenseForm, { groupId: activeGroupId, voiceDraft: draft, onDone: () => onOpenChange(false), onCancel: () => onOpenChange(false) })] })) : null] }) }));
}
function VoiceDraftSummary({ draft }) {
    const notices = [];
    if (draft.category.status === "ambiguous") {
        notices.push(`Категория «${draft.category.raw_text}» неоднозначна (варианты: ${draft.category.candidates
            .map((c) => c.name)
            .join(", ")}) — выберите ниже.`);
    }
    else if (draft.category.status === "unresolved" && draft.category.raw_text) {
        notices.push(`Не удалось определить категорию по фразе «${draft.category.raw_text}» — выберите ниже.`);
    }
    if (draft.payer.status === "ambiguous") {
        notices.push(`Плательщик «${draft.payer.raw_text}» неоднозначен (варианты: ${draft.payer.candidates
            .map((c) => c.user.name)
            .join(", ")}) — выберите ниже.`);
    }
    else if (draft.payer.status === "unresolved" && draft.payer.raw_text) {
        notices.push(`Не удалось определить, кто заплатил («${draft.payer.raw_text}») — выберите ниже.`);
    }
    for (const ambiguous of draft.participants.ambiguous) {
        notices.push(`«${ambiguous.raw_text}» — неоднозначно (варианты: ${ambiguous.candidates
            .map((c) => c.user.name)
            .join(", ")}) — добавьте участника вручную ниже.`);
    }
    if (draft.participants.unresolved.length > 0) {
        notices.push(`Не нашли среди участников группы: ${draft.participants.unresolved.join(", ")} — добавьте вручную, если нужно.`);
    }
    const hasNotices = notices.length > 0 || draft.warnings.length > 0;
    return (_jsxs("div", { className: "mt-2.5 flex flex-col gap-3 rounded-[22px] bg-subtle px-5 py-4 sm:px-6", children: [_jsxs("p", { className: "flex items-start gap-2.5 text-[15px] italic text-foreground", children: [_jsx(Quote, { className: "mt-0.5 size-4 shrink-0 text-faint", "aria-hidden": "true" }), _jsx("span", { className: "[overflow-wrap:anywhere]", children: draft.transcript })] }), hasNotices ? (_jsxs("ul", { className: cn("flex flex-col gap-1.5 border-t border-border pt-3"), children: [draft.warnings.map((warning) => (_jsxs("li", { className: "flex items-start gap-2 text-[13px] text-dim", children: [_jsx(AlertTriangle, { className: "mt-0.5 size-3.5 shrink-0", "aria-hidden": "true" }), _jsx("span", { children: warning })] }, warning))), notices.map((notice) => (_jsxs("li", { className: "flex items-start gap-2 text-[13px] text-dim", children: [_jsx(AlertTriangle, { className: "mt-0.5 size-3.5 shrink-0", "aria-hidden": "true" }), _jsx("span", { children: notice })] }, notice)))] })) : null] }));
}
