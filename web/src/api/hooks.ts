import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import { getJson, postJson } from './client';
import type {
  PostMessageBody,
  RunsFilter,
  UiAutomation,
  UiRun,
  UiRunDetail,
  UiTrigger,
} from './types';

const POLL_MS = 3000;

export function useAutomations() {
  return useQuery<UiAutomation[]>({
    queryKey: ['automations'],
    queryFn: () => getJson<UiAutomation[]>('/automations'),
    refetchInterval: POLL_MS,
  });
}

export function useTriggers() {
  return useQuery<UiTrigger[]>({
    queryKey: ['triggers'],
    queryFn: () => getJson<UiTrigger[]>('/triggers'),
    refetchInterval: POLL_MS,
  });
}

export function useRuns(filter: RunsFilter) {
  const qs = filter === 'all' ? '' : `?filter=${filter}`;
  return useQuery<UiRun[]>({
    queryKey: ['runs', filter],
    queryFn: () => getJson<UiRun[]>(`/runs${qs}`),
    refetchInterval: POLL_MS,
  });
}

export function useAutomationRuns(automationId: string | null) {
  return useQuery<UiRun[]>({
    queryKey: ['automation-runs', automationId],
    queryFn: () =>
      getJson<UiRun[]>(`/automations/${automationId}/runs`),
    refetchInterval: POLL_MS,
    enabled: automationId !== null,
  });
}

export function useRun(runId: number | null) {
  return useQuery<UiRunDetail>({
    queryKey: ['run', runId],
    queryFn: () => getJson<UiRunDetail>(`/runs/${runId}`),
    enabled: runId !== null,
    refetchInterval: POLL_MS,
  });
}

export function useRuns_byIds(runIds: number[]) {
  return useQueries({
    queries: runIds.map((id) => ({
      queryKey: ['run', id] as const,
      queryFn: () => getJson<UiRunDetail>(`/runs/${id}`),
      refetchInterval: POLL_MS,
    })),
  });
}

export function useStopRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: number) => postJson<{ ok: boolean }>(`/runs/${runId}/stop`),
    onSettled: (_data, _err, runId) => {
      qc.invalidateQueries({ queryKey: ['run', runId] });
      qc.invalidateQueries({ queryKey: ['runs'] });
      qc.invalidateQueries({ queryKey: ['automation-runs'] });
      qc.invalidateQueries({ queryKey: ['automations'] });
    },
  });
}

export function useRetryRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: number) =>
      postJson<{ ok: boolean; run_id?: number }>(`/runs/${runId}/retry`),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['runs'] });
      qc.invalidateQueries({ queryKey: ['automation-runs'] });
      qc.invalidateQueries({ queryKey: ['automations'] });
    },
  });
}

export function useSendMessage(runId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PostMessageBody) =>
      postJson<{ ok: boolean; seq: number }>(`/runs/${runId}/messages`, body),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['run', runId] });
    },
  });
}
