import { AlertTriangle, ChevronRight, Loader2, Mic, MicOff, Quote, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { GroupAvatar } from "@/components/common/GroupAvatar";
import { LoadingState } from "@/components/common/LoadingState";
import { ExpenseForm } from "@/components/expenses/ExpenseForm";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGroups } from "@/hooks/useGroups";
import { useCreateVoiceExpenseDraft } from "@/hooks/useVoiceExpense";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { VoiceExpenseDraft } from "@/types/api";

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

type Stage = "idle" | "recording" | "processing" | "review" | "error";

/** Preference order — the browser picks the first it actually supports. */
const CANDIDATE_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return CANDIDATE_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}

function isRecordingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function stopStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function VoiceExpenseDialog({ open, onOpenChange, groupId }: VoiceExpenseDialogProps) {
  const [pickedGroupId, setPickedGroupId] = useState<string | undefined>(undefined);
  const [stage, setStage] = useState<Stage>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [draft, setDraft] = useState<VoiceExpenseDraft | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

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
    if (!groupId) setPickedGroupId(undefined);
  };

  // Recording must not keep running (or the mic light stay on) once the
  // dialog is closed some other way — the close button, Esc, outside click.
  useEffect(() => {
    if (!open) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => () => reset(), []);

  async function handleUpload(blob: Blob) {
    setStage("processing");
    try {
      const result = await createDraft.mutateAsync(blob);
      setDraft(result);
      setStage("review");
    } catch (error) {
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
        if (event.data.size > 0) chunksRef.current.push(event.data);
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
    } catch {
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={stage === "review" || showGroupPicker ? undefined : "sm:max-w-[480px]"}
        onOpenAutoFocus={(event) => {
          if (stage === "review" || showGroupPicker) event.preventDefault();
        }}
      >
        <DialogHeader className="space-y-[5px]">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {showGroupPicker && "В какую группу добавить расход?"}
            {!showGroupPicker && stage === "idle" &&
              "Опишите расход голосом — распознаем сумму, категорию и участников."}
            {!showGroupPicker && stage === "recording" &&
              "Говорите, потом нажмите на квадрат, чтобы остановить."}
            {!showGroupPicker && stage === "processing" &&
              "Расшифровываем запись и извлекаем данные локально."}
            {!showGroupPicker && stage === "review" &&
              "Проверьте, что мы распознали, и поправьте, что нужно."}
            {!showGroupPicker && stage === "error" && "Можно попробовать ещё раз."}
          </DialogDescription>
        </DialogHeader>

        {showGroupPicker ? (
          <div className="flex flex-col gap-2">
            {groupsQuery.isPending ? (
              <LoadingState label="Загружаем ваши группы…" />
            ) : groupsQuery.isError ? (
              <ErrorState error={groupsQuery.error} onRetry={() => void groupsQuery.refetch()} />
            ) : groupsQuery.data.length === 0 ? (
              <p className="px-1 py-4 text-[15px] text-muted-foreground">
                Групп пока нет — создайте группу, чтобы добавить расход.
              </p>
            ) : (
              groupsQuery.data.map((group) => (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => setPickedGroupId(group.id)}
                  className="flex w-full items-center gap-3.5 rounded-row bg-subtle px-4 py-3.5 text-left transition-colors hover:bg-subtle-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <GroupAvatar group={group} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] font-semibold text-foreground">
                      {group.name}
                    </span>
                    <span className="block text-[13px] text-dim">
                      {plural(group.member_count, "участник", "участника", "участников")}
                    </span>
                  </span>
                  <ChevronRight className="size-[18px] shrink-0 text-faint" aria-hidden="true" />
                </button>
              ))
            )}
          </div>
        ) : null}

        {!showGroupPicker && stage === "idle" ? (
          <div className="flex flex-col items-center justify-center gap-5 px-5 py-9 text-center sm:px-6 sm:py-10">
            {supported ? (
              <button
                type="button"
                onClick={() => void startRecording()}
                aria-label="Начать запись"
                className="flex size-24 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-green transition-transform hover:bg-primary-hover active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Mic className="size-9" aria-hidden="true" />
              </button>
            ) : (
              <span className="flex size-24 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <MicOff className="size-9" aria-hidden="true" />
              </span>
            )}
            <p className="max-w-[36ch] text-[15px] text-muted-foreground">
              {supported
                ? "Нажмите на микрофон и назовите сумму, за что заплатили и с кем делите."
                : "Браузер не поддерживает запись звука. Попробуйте другой браузер или введите расход вручную."}
            </p>
          </div>
        ) : null}

        {!showGroupPicker && stage === "recording" ? (
          <div className="flex flex-col items-center justify-center gap-5 px-5 py-9 text-center sm:px-6 sm:py-10">
            <div className="relative flex size-24 shrink-0 items-center justify-center">
              <span
                className="absolute inset-0 animate-pulse rounded-full bg-destructive/20"
                aria-hidden="true"
              />
              <button
                type="button"
                onClick={stopRecording}
                aria-label="Остановить запись"
                className="relative flex size-24 shrink-0 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-green transition-transform active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Square className="size-8 fill-current" aria-hidden="true" />
              </button>
            </div>
            <p
              className="text-[28px] font-bold tabular-nums-money leading-none tracking-[-0.02em] text-foreground"
              aria-live="polite"
            >
              {formatElapsed(elapsedSeconds)}
            </p>
            <Button variant="secondary" size="sm" onClick={cancelRecording}>
              Отменить
            </Button>
          </div>
        ) : null}

        {!showGroupPicker && stage === "processing" ? (
          <div className="flex flex-col items-center justify-center gap-3 px-5 py-9 text-center sm:px-6 sm:py-10">
            <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground">
              <Loader2 className="size-6 animate-spin" aria-hidden="true" />
            </span>
            <p className="text-[15px] font-semibold text-foreground">
              Распознаём речь и данные о расходе…
            </p>
            <p className="max-w-[36ch] text-[13px] text-dim">
              Whisper и Qwen работают локально — это может занять до пары минут.
            </p>
          </div>
        ) : null}

        {!showGroupPicker && stage === "error" ? (
          <div className="flex flex-col items-center justify-center gap-4 px-5 py-9 text-center sm:px-6 sm:py-10">
            <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-negative">
              <AlertTriangle className="size-6" aria-hidden="true" />
            </span>
            <p className="mx-auto max-w-[44ch] text-[15px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
              {errorText}
            </p>
            <Button type="button" size="sm" onClick={reset}>
              Попробовать снова
            </Button>
          </div>
        ) : null}

        {!showGroupPicker && stage === "review" && draft && activeGroupId ? (
          <>
            <VoiceDraftSummary draft={draft} />
            <ExpenseForm
              groupId={activeGroupId}
              voiceDraft={draft}
              onDone={() => onOpenChange(false)}
              onCancel={() => onOpenChange(false)}
            />
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function VoiceDraftSummary({ draft }: { draft: VoiceExpenseDraft }) {
  const notices: string[] = [];

  if (draft.category.status === "ambiguous") {
    notices.push(
      `Категория «${draft.category.raw_text}» неоднозначна (варианты: ${draft.category.candidates
        .map((c) => c.name)
        .join(", ")}) — выберите ниже.`,
    );
  } else if (draft.category.status === "unresolved" && draft.category.raw_text) {
    notices.push(`Не удалось определить категорию по фразе «${draft.category.raw_text}» — выберите ниже.`);
  }

  if (draft.payer.status === "ambiguous") {
    notices.push(
      `Плательщик «${draft.payer.raw_text}» неоднозначен (варианты: ${draft.payer.candidates
        .map((c) => c.user.name)
        .join(", ")}) — выберите ниже.`,
    );
  } else if (draft.payer.status === "unresolved" && draft.payer.raw_text) {
    notices.push(`Не удалось определить, кто заплатил («${draft.payer.raw_text}») — выберите ниже.`);
  }

  for (const ambiguous of draft.participants.ambiguous) {
    notices.push(
      `«${ambiguous.raw_text}» — неоднозначно (варианты: ${ambiguous.candidates
        .map((c) => c.user.name)
        .join(", ")}) — добавьте участника вручную ниже.`,
    );
  }
  if (draft.participants.unresolved.length > 0) {
    notices.push(
      `Не нашли среди участников группы: ${draft.participants.unresolved.join(", ")} — добавьте вручную, если нужно.`,
    );
  }

  const hasNotices = notices.length > 0 || draft.warnings.length > 0;

  return (
    <div className="mt-2.5 flex flex-col gap-3 rounded-[22px] bg-subtle px-5 py-4 sm:px-6">
      <p className="flex items-start gap-2.5 text-[15px] italic text-foreground">
        <Quote className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden="true" />
        <span className="[overflow-wrap:anywhere]">{draft.transcript}</span>
      </p>
      {hasNotices ? (
        <ul className={cn("flex flex-col gap-1.5 border-t border-border pt-3")}>
          {draft.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-2 text-[13px] text-dim">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{warning}</span>
            </li>
          ))}
          {notices.map((notice) => (
            <li key={notice} className="flex items-start gap-2 text-[13px] text-dim">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{notice}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
