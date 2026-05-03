import type { JSX } from 'react';
import { useState } from 'react';

import type { UiRun } from '../../api/types';
import { fmtCost, fmtDuration, pluralRu } from '../../lib/format';
import type { TreeNode } from '../../lib/eventTree';
import {
  classifyNode,
  lastActionLabel,
  summarizeTree,
} from '../../lib/eventTree';
import { EventTree } from '../EventTree';
import {
  IconBolt,
  IconBranch,
  IconCheck,
  IconChevDown,
} from '../icons';

interface Props {
  run: UiRun;
  tree: TreeNode[];
  subagentCount: number;
}

function GlyphFor({ node }: { node: TreeNode | null }): JSX.Element | null {
  if (!node) return null;
  const k = classifyNode(node.event);
  if (k === 'tool') return <span>⚙</span>;
  if (k === 'thinking') return <span>◇</span>;
  if (k === 'subagent') return <IconBranch />;
  if (k === 'skill') return <IconBolt />;
  if (k === 'final') return <IconCheck />;
  return <span>▸</span>;
}

function lastGlyphKind(node: TreeNode | null): string {
  if (!node) return 'thinking';
  const k = classifyNode(node.event);
  if (k === 'tool' || k === 'skill' || k === 'subagent' || k === 'final') {
    return k;
  }
  return 'thinking';
}

export function ProcessZone({ run, tree, subagentCount }: Props): JSX.Element {
  const [open, setOpen] = useState(false);
  const summary = summarizeTree(tree);
  const isRunning = run.status === 'running';
  const stepsLabel = pluralRu(summary.steps, ['шаг', 'шага', 'шагов']);

  return (
    <section className="v3-zone v3-zone-process">
      <div className="v3-zone-label">
        <span>
          Процесс · {summary.steps} {stepsLabel}
        </span>
        {isRunning && <span className="v3-process-live">live</span>}
      </div>

      {!open && (
        <button
          className={`v3-process-collapsed ${isRunning ? 'live' : ''}`}
          onClick={() => setOpen(true)}
        >
          <span className="v3-process-counter">
            <b>{summary.steps}</b> {stepsLabel}
          </span>
          <span className="v3-process-sep">·</span>
          <span className="v3-process-last">
            {isRunning ? 'сейчас:' : 'последнее:'}
            <span className={`v3-tree-glyph ${lastGlyphKind(summary.last)}`}>
              <GlyphFor node={summary.last} />
            </span>
            <span className="v3-process-last-text">
              {lastActionLabel(summary.last)}
            </span>
            {isRunning && <span className="live-caret"></span>}
          </span>
          <span className="v3-process-sep">·</span>
          <span className="v3-process-stat">{fmtDuration(run.duration_sec)}</span>
          <span className="v3-process-sep">·</span>
          <span className="v3-process-stat">{fmtCost(run.cost_usd)}</span>
          {subagentCount > 0 && (
            <>
              <span className="v3-process-sep">·</span>
              <span className="v3-process-stat">{subagentCount} sub-agent</span>
            </>
          )}
          <span className="v3-process-spacer" />
          <span className="v3-process-hint">нажмите чтобы развернуть ↓</span>
        </button>
      )}

      {open && (
        <div className="v3-process-expanded">
          <div className="v3-process-toolbar">
            <button
              className="v3-process-collapse"
              onClick={() => setOpen(false)}
            >
              <IconChevDown
                style={{
                  width: 11,
                  height: 11,
                  transform: 'rotate(180deg)',
                }}
              />
              свернуть
            </button>
          </div>
          <div className="v3-tree-inline">
            {tree.length === 0 ? (
              <div className="v2-pane-info">Событий пока нет</div>
            ) : (
              <EventTree nodes={tree} />
            )}
          </div>
        </div>
      )}
    </section>
  );
}
