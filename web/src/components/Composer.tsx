import type { JSX } from 'react';
import { useState } from 'react';

import { useSendMessage } from '../api/hooks';
import type { PostMessageBody, UiRun } from '../api/types';
import { IconChevRight, IconStop } from './icons';

interface Props {
  run: UiRun;
}

export function Composer({ run }: Props): JSX.Element {
  const [text, setText] = useState('');
  const send = useSendMessage(run.id);

  const isRunning = run.status === 'running';
  const isWaiting = run.status === 'waiting';

  const placeholder = isRunning
    ? 'Добавить сообщение в очередь, агент увидит его на следующем шаге…'
    : isWaiting
      ? 'Ответьте чтобы продолжить…'
      : `Продолжить session — новый attempt #${run.session_seq + 1}`;

  const messageType: PostMessageBody['type'] = isRunning
    ? 'enqueue'
    : isWaiting
      ? 'reply'
      : 'continue';

  const submit = (): void => {
    const trimmed = text.trim();
    if (!trimmed) return;
    send.mutate(
      { type: messageType, text: trimmed },
      { onSuccess: () => setText('') },
    );
  };

  return (
    <div className="v2-composer">
      <div className="v2-composer-field">
        <textarea
          className="v2-composer-input"
          placeholder={placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <div className="v2-composer-actions">
          <span className="v2-composer-hint">
            session:{' '}
            <span style={{ color: 'var(--accent)' }}>{run.session_id}</span>
            {isRunning && (
              <span style={{ color: 'var(--running)', marginLeft: 8 }}>
                ⏵ агент работает — попадёт в очередь
              </span>
            )}
            {isWaiting && (
              <span style={{ color: 'var(--highlight)', marginLeft: 8 }}>
                ⏸ агент ждёт ответа
              </span>
            )}
          </span>
          {isRunning && (
            <button
              className="v2-composer-stop"
              type="button"
              disabled
              title="Stop доступен в шапке"
            >
              <IconStop style={{ width: 10, height: 10 }} /> stop
            </button>
          )}
          <button
            className={`v2-composer-send ${text.trim() ? 'active' : ''}`}
            type="button"
            disabled={!text.trim() || send.isPending}
            onClick={submit}
          >
            {messageType}
            <IconChevRight style={{ width: 10, height: 10 }} />
          </button>
        </div>
      </div>
    </div>
  );
}
