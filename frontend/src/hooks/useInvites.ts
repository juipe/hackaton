import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Group, Invite, InviteCreated, InvitePreview, Uuid } from "@/types/api";

export function useGroupInvites(groupId: Uuid | undefined) {
  return useQuery({
    queryKey: ["invites", groupId],
    queryFn: () => api.get<Invite[]>(`/groups/${groupId}/invites`),
    enabled: Boolean(groupId),
  });
}

export function useCreateInvite(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (email: string) =>
      api.post<InviteCreated>(`/groups/${groupId}/invites`, { email }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invites", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["activity", groupId] });
    },
  });
}

export function useRevokeInvite(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: Uuid) => api.del<void>(`/invites/${inviteId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invites", groupId] });
    },
  });
}

/** Public: this is the one query that works while signed out. */
export function useInvitePreview(token: string | undefined) {
  return useQuery({
    queryKey: ["invite", token],
    queryFn: () => api.get<InvitePreview>(`/invites/${token}`),
    enabled: Boolean(token),
    retry: false,
  });
}

export function useAcceptInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => api.post<Group>(`/invites/${token}/accept`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["invite"] });
    },
  });
}
