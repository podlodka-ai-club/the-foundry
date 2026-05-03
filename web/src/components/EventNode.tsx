import type { JSX } from 'react';
import { useState } from 'react';

import type { UiEvent } from '../api/types';
import { fmtCost, fmtDuration } from '../lib/format';
import type { TreeNode } from '../lib/eventTree';
import { classifyNode } from '../lib/eventTree';
import { EventTree } from './EventTree';
import { IconBolt, IconBranch, IconCheck } from './icons';

interface Props {
  node: TreeNode;
  first: boolean;
  last: boolean;
  depth: number;
}

function payloadText(ev: UiEvent): string {
  const p = ev.payload;
  if (typeof p['text'] === 'string') return p['text'];
  if (typeof p['summary'] === 'string') return p['summary'];
  if (typeof p['content'] === 'string') return p['content'];
  return '';
}

export function EventNode({ node, first, last, depth }: Props): JSX.Element {
  const [open, setOpen] = useState(false);
  const ev = node.event;
  const kind = classifyNode(ev);

  if (kind === 'mark') {
    const label =
      (ev.payload['label'] as string | undefined) ??
      (ev.payload['kind'] as string | undefined) ??
      ev.kind;
    return (
      <div className="v2-mark">
        <span className="v2-mark-bullet"></span>
        <span className="v2-mark-label">{label}</span>
        <span className="v2-mark-line"></span>
      </div>
    );
  }

  if (kind === 'subagent') {
    const name =
      (ev.payload['name'] as string | undefined) ??
      ev.stage.replace(/^subagent:/, '');
    const summary = payloadText(ev);
    const duration =
      (ev.payload['duration_sec'] as number | undefined) ?? null;
    const cost =
      (ev.payload['cost_usd'] as number | undefined) ?? null;
    const isTop = depth === 0;
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
        id={`sa-${ev.seq}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph subagent">
            <IconBranch />
          </span>
        </div>
        <div className="v2-tree-body">
          <div className={`v2-sub ${isTop ? 'top' : ''}`}>
            <div
              className={`v2-sub-head ${open ? 'open' : ''}`}
              onClick={() => setOpen((o) => !o)}
            >
              <span className={`v2-sub-chev ${open ? 'open' : ''}`}>▸</span>
              <div style={{ minWidth: 0 }}>
                <div className="v2-sub-title">
                  <span className="v2-sub-tag">sub-agent</span>
                  <span className="v2-sub-name">{name}</span>
                </div>
                {summary && (
                  <div className="v2-sub-summary">{summary}</div>
                )}
              </div>
              <span className="v2-sub-stats">
                {fmtDuration(duration)} · {fmtCost(cost)}
              </span>
            </div>
            {open && node.children.length > 0 && (
              <div className="v2-sub-children">
                <EventTree nodes={node.children} depth={depth + 1} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (kind === 'skill') {
    const skill = ev.stage.replace(/^skill:/, '');
    const detail = payloadText(ev);
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph skill">
            <IconBolt />
          </span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-skill">
            <span className="label">skill</span>
            <span className="name">{skill}</span>
            {detail && <span className="detail">{detail}</span>}
          </div>
        </div>
      </div>
    );
  }

  if (kind === 'tool') {
    const toolName =
      (ev.payload['name'] as string | undefined) ??
      (ev.payload['tool'] as string | undefined) ??
      'tool';
    // Streaming normalizer (`_normalize_tool_event`) writes a per-tool
    // human-readable hint into `payload.detail` (file path / command / url
    // depending on tool). Fall back to text/summary/content for events
    // that don't go through the normalizer.
    const detail =
      (typeof ev.payload['detail'] === 'string'
        ? (ev.payload['detail'] as string)
        : '') || payloadText(ev);
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph tool">⚙</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-tool">
            <span className="v2-tree-tool-name">{toolName}</span>
            {detail && (
              <span className="v2-tree-tool-detail">{detail}</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (kind === 'thinking') {
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph thinking">◇</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-thinking">{payloadText(ev)}</div>
        </div>
      </div>
    );
  }

  if (kind === 'final') {
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph final">
            <IconCheck />
          </span>
        </div>
        <div className="v2-tree-body">
          <div style={{ fontSize: 12, color: 'var(--fg-1)' }}>
            {payloadText(ev) || 'done'}
          </div>
        </div>
      </div>
    );
  }

  if (kind === 'stage') {
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph">▸</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-tool">
            <span className="v2-tree-tool-name">stage:{ev.stage}</span>
            <span className="v2-tree-tool-detail">{ev.kind}</span>
          </div>
          {node.children.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <EventTree nodes={node.children} depth={depth + 1} />
            </div>
          )}
        </div>
      </div>
    );
  }

  if (kind === 'input') {
    const promptText = (ev.payload['prompt'] as string | undefined) ?? '';
    const backend = (ev.payload['backend'] as string | undefined) ?? '';
    const model = (ev.payload['model'] as string | undefined) ?? '';
    const preview = promptText.split('\n')[0] || '(empty prompt)';
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph">📥</span>
        </div>
        <div className="v2-tree-body">
          <details className="v2-input-block">
            <summary className="v2-input-head">
              <span className="v2-input-tag">input → {backend}{model && `:${model}`}</span>
              <span className="v2-input-preview">{preview}</span>
            </summary>
            <pre className="v2-input-body">{promptText}</pre>
          </details>
        </div>
      </div>
    );
  }

  if (kind === 'user') {
    return (
      <div
        className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
      >
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph">›</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-text" style={{ color: 'var(--accent)' }}>
            user: {payloadText(ev)}
          </div>
        </div>
      </div>
    );
  }

  // text
  return (
    <div
      className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}
    >
      <div className="v2-tree-rail">
        <span className="v2-tree-glyph">▸</span>
      </div>
      <div className="v2-tree-body">
        <div className="v2-tree-text">{payloadText(ev)}</div>
      </div>
    </div>
  );
}
