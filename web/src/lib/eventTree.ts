import type { UiEvent } from '../api/types';

export interface TreeNode {
  event: UiEvent;
  children: TreeNode[];
}

export function treeFromEvents(events: UiEvent[]): TreeNode[] {
  const bySeq = new Map<number, TreeNode>();
  const roots: TreeNode[] = [];
  const sorted = [...events].sort((a, b) => a.seq - b.seq);
  for (const e of sorted) {
    const node: TreeNode = { event: e, children: [] };
    bySeq.set(e.seq, node);
    if (e.parent_event_seq != null && bySeq.has(e.parent_event_seq)) {
      bySeq.get(e.parent_event_seq)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

export type NodeKind =
  | 'subagent'
  | 'skill'
  | 'tool'
  | 'thinking'
  | 'text'
  | 'final'
  | 'mark'
  | 'stage'
  | 'user'
  | 'input';

export function classifyNode(e: UiEvent): NodeKind {
  if (e.kind === 'mark' || e.stage === 'milestone') return 'mark';
  if (e.stage === 'run_lifecycle') return 'mark';
  if (e.stage === 'user_input') return 'user';
  if (e.kind === 'agent_input') return 'input';
  if (e.stage.startsWith('subagent:')) return 'subagent';
  if (e.kind === 'agent_tool') return 'tool';
  if (e.kind === 'agent_thinking') return 'thinking';
  if (e.kind === 'agent_text') return 'text';
  if (e.kind === 'agent_result') return 'final';
  if (e.stage.startsWith('skill:')) return 'skill';
  if (e.kind === 'stage_started' || e.kind === 'stage_finished' || e.kind === 'stage_failed') {
    return 'stage';
  }
  return 'text';
}

export function mergeBySeq(a: UiEvent[], b: UiEvent[]): UiEvent[] {
  const m = new Map<number, UiEvent>();
  for (const e of a) m.set(e.seq, e);
  for (const e of b) m.set(e.seq, e);
  return [...m.values()].sort((x, y) => x.seq - y.seq);
}

/**
 * Walk the tree recursively. Counts every step except `mark` rows
 * (milestones are visual dividers, not work). `last` is the most recent
 * step in document order — used to render the collapsed Process line.
 */
export function summarizeTree(roots: TreeNode[]): {
  steps: number;
  last: TreeNode | null;
} {
  let steps = 0;
  let last: TreeNode | null = null;
  const visit = (nodes: TreeNode[]): void => {
    for (const n of nodes) {
      if (classifyNode(n.event) === 'mark') continue;
      steps += 1;
      last = n;
      if (n.children.length > 0) visit(n.children);
    }
  };
  visit(roots);
  return { steps, last };
}

function eventText(e: UiEvent): string {
  const p = e.payload;
  if (typeof p['text'] === 'string') return p['text'];
  if (typeof p['summary'] === 'string') return p['summary'];
  if (typeof p['detail'] === 'string') return p['detail'];
  return '';
}

/** One-line label for the collapsed Process indicator. */
export function lastActionLabel(node: TreeNode | null): string {
  if (!node) return '—';
  const e = node.event;
  const kind = classifyNode(e);
  if (kind === 'tool') {
    const name =
      (e.payload['name'] as string | undefined) ??
      (e.payload['tool'] as string | undefined) ??
      'tool';
    const detail = (e.payload['detail'] as string | undefined) ?? eventText(e);
    return detail ? `${name} · ${detail}` : name;
  }
  if (kind === 'skill') {
    const skill = e.stage.replace(/^skill:/, '');
    const detail = eventText(e);
    return detail ? `skill ${skill} · ${detail}` : `skill ${skill}`;
  }
  if (kind === 'subagent') {
    const name = (e.payload['name'] as string | undefined) ?? e.stage.replace(/^subagent:/, '');
    return `sub-agent ${name}`;
  }
  if (kind === 'final') return `итог: ${eventText(e) || 'done'}`;
  if (kind === 'thinking') return eventText(e) || 'размышление';
  return eventText(e) || e.kind;
}

