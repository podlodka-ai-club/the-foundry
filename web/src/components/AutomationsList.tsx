import type { JSX } from 'react';

import { useAutomations } from '../api/hooks';
import { IconBolt } from './icons';
import { TriggersFooter } from './TriggersFooter';

interface Props {
  activeId: string | null;
  onSelect: (automationId: string) => void;
}

export function AutomationsList({ activeId, onSelect }: Props): JSX.Element {
  const { data, isLoading, error } = useAutomations();

  if (isLoading) {
    return <div className="v2-pane-info">Загрузка…</div>;
  }
  if (error) {
    return <div className="v2-pane-info">Ошибка загрузки automations</div>;
  }
  const automations = data ?? [];

  return (
    <div>
      <div className="v2-aut-list">
        {automations.map((a) => {
          const active = a.counts.running > 0 || a.counts.total > 0;
          return (
            <div
              key={a.id}
              className={`v2-aut-row ${activeId === a.id ? 'active' : ''}`}
              onClick={() => onSelect(a.id)}
            >
              <span className="v2-aut-icon"><IconBolt /></span>
              <div style={{ minWidth: 0 }}>
                <div className="v2-aut-name">{a.name}</div>
                <div className="v2-aut-desc">{a.description}</div>
              </div>
              <div className={`v2-aut-state ${active ? 'active' : ''}`}>
                {a.counts.running > 0
                  ? `${a.counts.running} running`
                  : 'Active'}
                <span className="v2-toggle"></span>
              </div>
            </div>
          );
        })}
        {automations.length === 0 && (
          <div className="v2-pane-info">Нет automations</div>
        )}
      </div>
      <TriggersFooter />
    </div>
  );
}
