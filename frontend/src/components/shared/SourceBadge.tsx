import React from "react";
import "./SourceBadge.css";
import { useDataStatus } from "../../hooks/useDataStatus";
import type { SourceStatus } from "../../api/dataStatus";

const STATUS_LABEL: Record<SourceStatus, string> = {
  real: "Live",
  static: "Static",
  mocked: "Mocked",
  pending: "Pending",
};

interface Props {
  /** Dataset key registered in backend/app/services/data_status.py. */
  datasetKey: string;
  /**
   * Override the registry value (e.g. when a widget already knows its source
   * inline — useful for IC3 routes that return their own `source` field).
   */
  fallbackStatus?: SourceStatus;
  fallbackSource?: string;
  className?: string;
}

const SourceBadge: React.FC<Props> = ({
  datasetKey,
  fallbackStatus,
  fallbackSource,
  className,
}) => {
  const { byKey, loading } = useDataStatus();
  const entry = byKey[datasetKey];

  const resolvedStatus: SourceStatus | null = entry?.status ?? fallbackStatus ?? null;
  const status: SourceStatus | "unknown" = resolvedStatus ?? "unknown";
  const source = entry?.source ?? fallbackSource ?? "Source not registered";
  const label = resolvedStatus === null ? (loading ? "…" : "?") : STATUS_LABEL[resolvedStatus];
  const title = `${label}: ${source}${entry?.notes ? ` · ${entry.notes}` : ""}`;

  return (
    <span
      className={`source-badge source-badge--${status}${className ? ` ${className}` : ""}`}
      title={title}
      data-dataset-key={datasetKey}
      aria-label={`Data source: ${label} — ${source}`}
    >
      <span className="source-badge__dot" aria-hidden="true" />
      {label}
    </span>
  );
};

export default SourceBadge;
