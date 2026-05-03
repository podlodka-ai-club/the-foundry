import type { JSX } from 'react';

interface Props {
  text: string;
}

export function Markdownish({ text }: Props): JSX.Element | null {
  if (!text) return null;
  const lines = text.split('\n');
  return (
    <>
      {lines.map((line, i) => {
        if (line.startsWith('## ')) {
          return (
            <div key={i} className="v3-md-h">
              {line.slice(3)}
            </div>
          );
        }
        if (/^- \[ \]/.test(line)) {
          return (
            <div key={i} className="v3-md-li">
              <span className="v3-md-cb"></span>
              {line.slice(5)}
            </div>
          );
        }
        if (/^- \[x\]/i.test(line)) {
          return (
            <div key={i} className="v3-md-li">
              <span className="v3-md-cb done"></span>
              {line.slice(5)}
            </div>
          );
        }
        if (line.startsWith('- ')) {
          return (
            <div key={i} className="v3-md-li">
              <span className="v3-md-bullet"></span>
              {line.slice(2)}
            </div>
          );
        }
        if (line.trim() === '') {
          return <div key={i} className="v3-md-spacer" />;
        }
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        return (
          <div key={i} className="v3-md-p">
            {parts.map((p, j) =>
              p.startsWith('**') && p.endsWith('**') ? (
                <b key={j}>{p.slice(2, -2)}</b>
              ) : (
                <span key={j}>{p}</span>
              ),
            )}
          </div>
        );
      })}
    </>
  );
}
