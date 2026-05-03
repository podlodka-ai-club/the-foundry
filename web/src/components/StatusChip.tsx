import type { JSX } from "react";
import { Check, X } from "lucide-react";

interface Props {
  status: string;
}

export default function StatusChip({ status }: Props): JSX.Element {
  const upper = status.toUpperCase();
  if (upper === "RUNNING") {
    return (
      <span className="chip chip-running">
        <span className="dot dot-running" />
        RUNNING
      </span>
    );
  }
  if (upper === "DONE") {
    return (
      <span className="chip chip-done">
        <Check className="ico-sm" />
        DONE
      </span>
    );
  }
  if (upper === "FAILED") {
    return (
      <span className="chip chip-failed">
        <X className="ico-sm" />
        FAILED
      </span>
    );
  }
  if (upper === "PENDING") {
    return (
      <span className="chip chip-pending">
        <span className="dot dot-pending" />
        PENDING
      </span>
    );
  }
  return <span className="chip chip-pending">{upper}</span>;
}
