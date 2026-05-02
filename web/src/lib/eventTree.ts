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
  | 'user';

export function classifyNode(e: UiEvent): NodeKind {
  if (e.kind === 'mark' || e.stage === 'milestone') return 'mark';
  if (e.stage === 'run_lifecycle') return 'mark';
  if (e.stage === 'user_input') return 'user';
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
