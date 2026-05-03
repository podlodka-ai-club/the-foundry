// Compact monochrome SVG icon set ported from the design (Lucide-style).
// All 14×14 by default, stroke=1.5, currentColor.

import type { JSX, SVGProps } from 'react';

type P = SVGProps<SVGSVGElement>;

const base = (props: P): P => ({
  width: 14,
  height: 14,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  ...props,
});

export const IconBolt = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M13 2L4 14h7l-1 8 9-12h-7z" />
  </svg>
);

export const IconBranch = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <circle cx="6" cy="5" r="2" />
    <circle cx="6" cy="19" r="2" />
    <circle cx="18" cy="7" r="2" />
    <path d="M6 7v10M6 13c0-4 4-4 4-4h6" />
  </svg>
);

export const IconInbox = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M3 13l4-9h10l4 9v6H3z" />
    <path d="M3 13h5l1 3h6l1-3h5" />
  </svg>
);

export const IconChevLeft = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M15 6l-6 6 6 6" />
  </svg>
);

export const IconChevRight = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M9 6l6 6-6 6" />
  </svg>
);

export const IconCheck = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M5 13l4 4L19 7" />
  </svg>
);

export const IconRefresh = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);

export const IconExternal = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M14 4h6v6" />
    <path d="M20 4L10 14" />
    <path d="M20 14v6H4V4h6" />
  </svg>
);

export const IconStop = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <rect x="6" y="6" width="12" height="12" rx="1" />
  </svg>
);

export const IconSparkle = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" />
  </svg>
);

export const IconWebhook = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M9 8a3 3 0 1 1 5.5 1.5l3 5" />
    <path d="M14 17a3 3 0 1 1-3-3l3-5" />
    <path d="M5 17a3 3 0 1 1 3 3h6" />
  </svg>
);

export const IconClock = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const IconGitHub = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.3-3.4-1.3-.5-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8 0-.6.3-1.1.6-1.4-2.2-.2-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.5-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .6 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.8v2.7c0 .3.2.6.7.5A10 10 0 0 0 12 2z" />
  </svg>
);

export const IconDiscord = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M19 5a16 16 0 0 0-4-1l-.3.6a13 13 0 0 0-5.4 0L9 4a16 16 0 0 0-4 1C2 9 1.5 13 2 17c1.6 1.2 3.2 2 4.7 2.5l1-1.5c-.9-.3-1.7-.7-2.4-1.2.2-.1.4-.3.6-.4a11 11 0 0 0 10.2 0l.6.4c-.7.5-1.5.9-2.4 1.2l1 1.5c1.5-.5 3.1-1.3 4.7-2.5.6-4.7-.3-8.6-3-12z" />
  </svg>
);

export const IconChat = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M4 5h16v11H8l-4 4z" />
  </svg>
);

export const IconX = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

export const IconChevDown = (p: P): JSX.Element => (
  <svg {...base(p)}>
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export function triggerKindIcon(kind: string): (p: P) => JSX.Element {
  if (kind === 'github' || kind === 'github_issues' || kind.startsWith('issue.') || kind.startsWith('pr.')) return IconGitHub;
  if (kind === 'discord') return IconDiscord;
  if (kind === 'telegram' || kind === 'message') return IconChat;
  if (kind === 'cron' || kind === 'cron.tick') return IconClock;
  return IconWebhook;
}
