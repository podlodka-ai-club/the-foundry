// Semantic verdicts the agent can return alongside a DONE lifecycle. Mirrors
// `DONE_OUTCOMES` in src/foundry/status_marker.py — keep both in sync.

export type OutcomeTone = 'success' | 'warning' | 'danger' | 'neutral';

export const OUTCOME_TONE: Record<string, OutcomeTone> = {
  approved: 'success',
  change_requested: 'warning',
  rejected: 'danger',
};

export const OUTCOME_LABEL: Record<string, string> = {
  approved: 'approved',
  change_requested: 'change requested',
  rejected: 'rejected',
};

export function outcomeTone(outcome: string | null | undefined): OutcomeTone {
  if (!outcome) return 'neutral';
  return OUTCOME_TONE[outcome] ?? 'neutral';
}

export function outcomeLabel(outcome: string | null | undefined): string {
  if (!outcome) return '';
  return OUTCOME_LABEL[outcome] ?? outcome.replace(/_/g, ' ');
}
