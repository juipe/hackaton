import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Uuid, VoiceExpenseDraft } from "@/types/api";

/**
 * Загружает фото чека и получает эфемерный черновик расхода — ничего не
 * сохраняется. Подтверждение черновика идёт через обычный
 * `useCreateExpense(groupId)`, как и ручной ввод (та же форма ответа, что у
 * голосового черновика).
 */
export function useCreateReceiptExpenseDraft(groupId: Uuid) {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("receipt", file, file.name || "receipt.jpg");
      return api.post<VoiceExpenseDraft>(`/groups/${groupId}/receipt-expenses`, form);
    },
  });
}
