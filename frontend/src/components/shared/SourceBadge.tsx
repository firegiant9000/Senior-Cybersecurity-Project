import React from "react";
import "./SourceBadge.css";
import { useDataStatus } from "../../hooks/useDataStatus";
import type { SourceStatus } from "../../api/dataStatus";
import { leastConfident } from "./sourceConfidence";

const STATUS_LABEL: Record<SourceStatus, string> = {
  real: "Live",
  static: "Static",
  mocked: "Mocked",
  pending: "Pending",
};

type KeyProps =
  /** Dataset key registered in backend/app/services/data_status.py. */
  | {
      datasetKey: string;
      datasetKeys?: never;
      /**
       * Override the registry value (e.g. when a widget already knows its
       * source inline — useful for IC3 routes that return their own `source`
       * field). Single-key mode only: with several keys a fallback could mask
       * an unregistered dataset and overstate confidence.
       */
      fallbackStatus?: SourceStatus;
      fallbackSource?: string;
    }
  /** Several datasets feeding one card: shows the least confident status. */
  | {
      datasetKeys: string[];
      datasetKey?: never;
      fallbackStatus?: never;
      fallbackSource?: never;
    };

type Props = KeyProps & { className?: string };

const SourceBadge: React.FC<Props> = ({
  datasetKey,
  datasetKeys,
  fallbackStatus,
  fallbackSource,
  className,
}) => {
  const { byKey, loading } = useDataStatus();
  const keys = datasetKeys ?? (datasetKey !== undefined ? [datasetKey] : []);
  const entries = keys.map((k) => byKey[k]);

  // An unregistered key resolves to unknown (null), never to a confident status.
  const resolvedStatus: SourceStatus | null = datasetKeys
    ? leastConfident(entries.map((e) => e?.status ?? null))
    : (entries[0]?.status ?? fallbackStatus ?? null);
  const status: SourceStatus | "unknown" = resolvedStatus ?? "unknown";
  const source = datasetKeys
    ? datasetKeys.length
      ? datasetKeys.map((k, i) => entries[i]?.source ?? `unregistered (${k})`).join(" + ")
      : "Source not registered"
    : (entries[0]?.source ?? fallbackSource ?? "Source not registered");
  const label = resolvedStatus === null ? (loading ? "…" : "?") : STATUS_LABEL[resolvedStatus];
  const notes = entries.length === 1 ? entries[0]?.notes : null;
  const title = `${label}: ${source}${notes ? ` · ${notes}` : ""}`;

  return (
    <span
      className={`source-badge source-badge--${status}${className ? ` ${className}` : ""}`}
      title={title}
      data-dataset-key={keys.join(",")}
      aria-label={`Data source: ${label} — ${source}`}
    >
      <span className="source-badge__dot" aria-hidden="true" />
      {label}
    </span>
  );
};

export default SourceBadge;
