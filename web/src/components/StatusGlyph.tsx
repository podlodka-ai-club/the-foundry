import type { JSX } from 'react';

import type { RunStatus } from '../api/types';
import { IconCheck } from './icons';

interface Props {
  status: RunStatus;
  size?: number;
}

export function StatusGlyph({ status, size }: Props): JSX.Element {
  const cls = status;
  const style = size ? { width: size, height: size } : undefined;
  return (
    <span className={`v2-glyph ${cls}`} style={style}>
      {status === 'done' && <IconCheck />}
    </span>
  );
}
