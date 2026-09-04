import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Uuid, VoiceExpenseDraft } from "@/types/api";

/**
 * Uploads a recorded voice note and gets back an ephemeral draft — nothing is
 * persisted here. Confirming the draft goes through the existing
 * `useCreateExpense(groupId)` mutation, same as manual entry.
 */
export function useCreateVoiceExpenseDraft(groupId: Uuid) {
  return useMutation({
    mutationFn: (audio: Blob) => {
      const form = new FormData();
      const extension = audio.type.includes("ogg") ? "ogg" : audio.type.includes("mp4") ? "mp4" : "webm";
      form.append("audio", audio, `voice-expense.${extension}`);
      return api.post<VoiceExpenseDraft>(`/groups/${groupId}/voice-expenses`, form);
    },
  });
}
