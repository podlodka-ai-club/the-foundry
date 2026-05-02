import { useEffect, useState } from 'react';

import type { UiEvent } from './types';

export interface RunStreamState {
  events: UiEvent[];
  connected: boolean;
}

export function useRunStream(runId: number | null): RunStreamState {
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (runId === null) {
      setEvents([]);
      setConnected(false);
      return;
    }
    setEvents([]);
    setConnected(false);
    const es = new EventSource(`/api/runs/${runId}/events`);
    es.onopen = () => setConnected(true);
    es.addEventListener('run_event', (e: MessageEvent) => {
      try {
        const ev = JSON.parse(e.data) as UiEvent;
        setEvents((prev) =>
          prev.find((x) => x.seq === ev.seq) ? prev : [...prev, ev],
        );
      } catch {
        // ignore malformed payloads
      }
    });
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
    };
  }, [runId]);

  return { events, connected };
}
