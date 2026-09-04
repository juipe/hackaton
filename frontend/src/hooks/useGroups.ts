import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  Group,
  GroupCreateInput,
  GroupUpdateInput,
  Member,
  Uuid,
} from "@/types/api";

export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: () => api.get<Group[]>("/groups"),
  });
}

export function useGroup(groupId: Uuid | undefined) {
  return useQuery({
    queryKey: ["group", groupId],
    queryFn: () => api.get<Group>(`/groups/${groupId}`),
    enabled: Boolean(groupId),
  });
}

export function useMembers(groupId: Uuid | undefined) {
  return useQuery({
    queryKey: ["members", groupId],
    queryFn: () => api.get<Member[]>(`/groups/${groupId}/members`),
    enabled: Boolean(groupId),
  });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GroupCreateInput) => api.post<Group>("/groups", input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateGroup(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GroupUpdateInput) => api.patch<Group>(`/groups/${groupId}`, input),
    onSuccess: (group) => {
      queryClient.setQueryData(["group", groupId], group);
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["activity", groupId] });
    },
  });
}

export function useDeleteGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (groupId: Uuid) => api.del<void>(`/groups/${groupId}`),
    onSuccess: (_data, groupId) => {
      queryClient.removeQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRemoveMember(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: Uuid) => api.del<void>(`/groups/${groupId}/members/${userId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["members", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["balances", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
}
