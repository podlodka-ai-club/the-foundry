import type { FailureKind, RunStatus } from '../api/types';

export const STATUS_GLYPH: Record<RunStatus, string> = {
  pending: '·',
  running: '◔',
  waiting: '◐',
  done: '●',
  failed: '✖',
  unclear: '?',
};

export const STATUS_WORD: Record<RunStatus, string> = {
  pending: 'pending',
  running: 'running',
  waiting: 'waiting',
  done: 'done',
  failed: 'failed',
  unclear: 'unclear',
};

export const FAILURE_LABEL: Record<FailureKind, string> = {
  deterministic: 'Тесты/lint',
  acceptance: 'Не по задаче',
  infra: 'Инфра',
  unclear: 'Непонятно',
  dangerous: 'Опасно',
};

export const FAILURE_TOOLTIP: Record<FailureKind, string> = {
  deterministic: 'объективно сломано: тесты, lint, типы, build',
  acceptance: 'работает, но не делает то, что просили',
  infra: 'сетевой/CI флак — можно retry',
  unclear: 'verifier не разобрался, нужен человек',
  dangerous: 'действие требует ручного апрува',
};
