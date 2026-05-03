// StageIO — renders stage input/output payloads.
// Data can be:
//   - { kind: "kv", items: [[k, v], ...] }
//   - { kind: "files", label?, items: string[] }
//   - { kind: "text", label?, text: string }
//   - { kind: "error", label: string, text: string }
//   - { kind: "pending", label?: string }
//   - a plain object (fallback → kv render of own props)
//   - null / undefined → "нет данных"

import type { JSX } from "react";
import { useState } from "react";
import { File, Folder } from "lucide-react";

type IOData = Record<string, unknown> | null | undefined;

interface Props {
  kind?: "input" | "output";
  data: IOData;
}

const TEXT_HEIGHT_LIMIT = 180;

const KV_TRUNCATE_AT = 80;

function KVList({ items }: { items: [string, string][] }): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const hasLong = items.some(([, v]) => v.length > KV_TRUNCATE_AT || v.includes("\n"));
  return (
    <div>
      <dl
        style={{
          margin: 0,
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: "4px 12px",
          fontSize: 11.5,
        }}
      >
        {items.map(([k, v], i) => (
          <div key={`${i}-${k}`} style={{ display: "contents" }}>
            <dt className="mono" style={{ color: "var(--fg-3)" }}>
              {k}
            </dt>
            <dd
              className="mono"
              style={{
                color: "var(--fg-0)",
                margin: 0,
                overflow: "hidden",
                textOverflow: expanded ? "clip" : "ellipsis",
                whiteSpace: expanded ? "pre-wrap" : "nowrap",
                wordBreak: expanded ? "break-word" : "normal",
              }}
              title={expanded ? undefined : v}
            >
              {v}
            </dd>
          </div>
        ))}
      </dl>
      {hasLong && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          style={{
            marginTop: 6,
            fontSize: 11,
            color: "var(--accent)",
            cursor: "pointer",
          }}
        >
          {expanded ? "свернуть" : "показать всё"}
        </button>
      )}
    </div>
  );
}

function TextBlock({ text, label }: { text: string; label?: string }): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 400 || text.split("\n").length > 8;
  return (
    <div>
      {label && (
        <div
          style={{
            fontSize: 10.5,
            color: "var(--fg-3)",
            marginBottom: 4,
            letterSpacing: ".06em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
      )}
      <pre
        className="mono"
        style={{
          margin: 0,
          fontSize: 11.5,
          lineHeight: 1.5,
          color: "var(--fg-0)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: expanded ? "none" : TEXT_HEIGHT_LIMIT,
          overflow: expanded ? "visible" : "hidden",
          background: "transparent",
        }}
      >
        {text}
      </pre>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          style={{
            marginTop: 6,
            fontSize: 11,
            color: "var(--accent)",
            cursor: "pointer",
          }}
        >
          {expanded ? "свернуть" : "показать всё"}
        </button>
      )}
    </div>
  );
}

function FilesBlock({ label, items }: { label?: string; items: string[] }): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {label && (
        <div style={{ fontSize: 11, color: "var(--fg-2)", marginBottom: 4 }}>{label}</div>
      )}
      {items.map((f, i) => (
        <div
          key={`${i}-${f}`}
          className="mono"
          style={{
            fontSize: 11.5,
            color: "var(--fg-1)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <File className="ico-sm" style={{ color: "var(--fg-3)" }} />
          {f}
        </div>
      ))}
    </div>
  );
}

function ErrorBlock({ label, text }: { label: string; text: string }): JSX.Element {
  return (
    <div>
      <div style={{ fontSize: 11.5, color: "var(--danger)", marginBottom: 4 }}>{label}</div>
      <pre
        className="mono"
        style={{
          margin: 0,
          fontSize: 11.5,
          color: "var(--fg-1)",
          whiteSpace: "pre-wrap",
        }}
      >
        {text}
      </pre>
    </div>
  );
}

function PendingBlock({ label }: { label?: string }): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        color: "var(--fg-2)",
        fontSize: 11.5,
      }}
    >
      <span className="spinner" />
      {label || "в процессе…"}
    </div>
  );
}

function Empty(): JSX.Element {
  return (
    <span className="dim" style={{ fontSize: 11.5 }}>
      нет данных
    </span>
  );
}

export default function StageIO({ data }: Props): JSX.Element {
  if (!data) return <Empty />;

  const kind = typeof data.kind === "string" ? (data.kind as string) : undefined;

  if (kind === "kv" && Array.isArray(data.items)) {
    const items = (data.items as unknown[]).filter(
      (it): it is [string, string] =>
        Array.isArray(it) && it.length === 2 && typeof it[0] === "string",
    );
    if (items.length === 0) return <Empty />;
    const normalized: [string, string][] = items.map(([k, v]) => [k, String(v)]);
    return <KVList items={normalized} />;
  }

  if (kind === "files" && Array.isArray(data.items)) {
    const items = (data.items as unknown[]).map(String);
    return <FilesBlock label={data.label as string | undefined} items={items} />;
  }

  if (kind === "text" && typeof data.text === "string") {
    return <TextBlock text={data.text} label={data.label as string | undefined} />;
  }

  if (kind === "error" && typeof data.text === "string") {
    return (
      <ErrorBlock
        label={(data.label as string | undefined) ?? "Ошибка"}
        text={data.text}
      />
    );
  }

  if (kind === "pending") {
    return <PendingBlock label={data.label as string | undefined} />;
  }

  // Stage output shape emitted by pipeline.py for plan/implement:
  // { summary: <first line>, text: <full agent response> }.
  if (typeof data.summary === "string" && typeof data.text === "string") {
    const summary = data.summary;
    const text = data.text;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div
          style={{
            fontSize: 12.5,
            color: "var(--fg-0)",
            fontWeight: 600,
            lineHeight: 1.4,
          }}
        >
          {summary || <span className="dim">—</span>}
        </div>
        {text && text !== summary && <TextBlock text={text} />}
      </div>
    );
  }

  // Fallback: render unknown dicts as key-value pairs.
  const entries = Object.entries(data).filter(
    ([k]) => k !== "kind" && k !== "truncated" && k !== "original_size",
  );
  if (entries.length === 0) return <Empty />;

  // Pull out long text fields (prompt, plan, text) into TextBlocks so they
  // render as raw collapsible text instead of one-line truncated kv values.
  const LONG_TEXT_KEYS = new Set(["prompt", "plan", "text"]);
  const kvEntries: [string, unknown][] = [];
  const textEntries: [string, string][] = [];
  for (const [k, v] of entries) {
    if (LONG_TEXT_KEYS.has(k) && typeof v === "string" && v.length > 0) {
      textEntries.push([k, v]);
    } else {
      kvEntries.push([k, v]);
    }
  }

  const folderIcon = <Folder className="ico-sm" style={{ display: "none" }} />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {folderIcon}
      {kvEntries.length > 0 && (
        <KVList items={kvEntries.map(([k, v]) => [k, stringify(v)])} />
      )}
      {textEntries.map(([k, v]) => (
        <TextBlock key={k} label={k} text={v} />
      ))}
    </div>
  );
}

function stringify(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}
