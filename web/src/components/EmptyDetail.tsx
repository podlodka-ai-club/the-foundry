import type { JSX } from 'react';

import { IconSparkle } from './icons';

export function EmptyDetail(): JSX.Element {
  return (
    <div className="v2-detail">
      <div className="v2-empty">
        <div className="v2-empty-inner">
          <IconSparkle className="icon" width={28} height={28} />
          <div className="title">Выберите run слева</div>
          <div className="sub">Дерево вызовов агента появится здесь</div>
        </div>
      </div>
    </div>
  );
}
