import type { JSX } from 'react';

import type { TreeNode } from '../lib/eventTree';
import { EventNode } from './EventNode';

interface Props {
  nodes: TreeNode[];
  depth?: number;
}

export function EventTree({ nodes, depth = 0 }: Props): JSX.Element {
  return (
    <div>
      {nodes.map((n, i) => (
        <EventNode
          key={n.event.seq}
          node={n}
          first={i === 0}
          last={i === nodes.length - 1}
          depth={depth}
        />
      ))}
    </div>
  );
}
