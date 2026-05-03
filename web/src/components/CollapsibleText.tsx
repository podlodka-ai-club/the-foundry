import type { JSX } from 'react';
import { useState } from 'react';

import { pluralRu } from '../lib/format';
import { Markdownish } from './Markdownish';

interface Props {
  text: string;
  threshold?: number;
  charLimit?: number;
  className?: string;
}

export function CollapsibleText({
  text,
  threshold = 2,
  charLimit = 180,
  className = '',
}: Props): JSX.Element | null {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  const lines = text.split('\n');
  const totalLines = lines.length;
  const long = totalLines > threshold || text.length > charLimit;
  if (!long) {
    return (
      <div className={`v3-text ${className}`}>
        <Markdownish text={text} />
      </div>
    );
  }

  let preview = lines.slice(0, threshold).join('\n');
  if (preview.length > charLimit) {
    const cut = preview.lastIndexOf(' ', charLimit);
    preview = preview.slice(0, cut > charLimit * 0.6 ? cut : charLimit);
  }
  const hiddenLines = totalLines - threshold;
  const hiddenChars = text.length - preview.length;

  return (
    <div className={`v3-text ${className} ${open ? 'open' : 'collapsed'}`}>
      <div className="v3-text-inner">
        <Markdownish text={open ? text : preview} />
        {!open && <span className="v3-text-fade" aria-hidden="true" />}
      </div>
      <button className="v3-text-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? (
          <>свернуть ↑</>
        ) : hiddenLines > 0 ? (
          <>
            показать ещё {hiddenLines}{' '}
            {pluralRu(hiddenLines, ['строку', 'строки', 'строк'])} ↓
          </>
        ) : (
          <>показать ещё {hiddenChars} символов ↓</>
        )}
      </button>
    </div>
  );
}
