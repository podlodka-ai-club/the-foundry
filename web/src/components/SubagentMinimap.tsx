import type { JSX } from 'react';

import { fmtDuration } from '../lib/format';
import type { TreeNode } from '../lib/eventTree';
import { classifyNode } from '../lib/eventTree';
import { IconBranch } from './icons';

interface Props {
  roots: TreeNode[];
}

export function SubagentMinimap({ roots }: Props): JSX.Element | null {
  const subs = roots.filter((n) => classifyNode(n.event) === 'subagent');
  if (subs.length === 0) return null;

  const scrollTo = (seq: number): void => {
    const el = document.getElementById(`sa-${seq}`);
    if (!el) return;
    const wrap = el.closest('.v2-tree-wrap');
    if (wrap instanceof HTMLElement) {
      const top = el.offsetTop - wrap.offsetTop - 30;
      wrap.scrollTo({ top, behavior: 'smooth' });
    }
  };

  return (
    <div className="v2-minimap">
      <span className="v2-minimap-label">sub-agents called</span>
      <div className="v2-minimap-track">
        {subs.map((s, i) => {
          const name =
            (s.event.payload['name'] as string | undefined) ??
            s.event.stage.replace(/^subagent:/, '');
          const dur =
            (s.event.payload['duration_sec'] as number | undefined) ?? null;
          return (
            <span key={s.event.seq} style={{ display: 'inline-flex' }}>
              {i > 0 && <span className="v2-minimap-sep">›</span>}
              <button
                className="v2-minimap-pill"
                onClick={() => scrollTo(s.event.seq)}
              >
                <IconBranch />
                <span>{name}</span>
                {dur !== null && (
                  <span className="v2-minimap-meta">{fmtDuration(dur)}</span>
                )}
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}
