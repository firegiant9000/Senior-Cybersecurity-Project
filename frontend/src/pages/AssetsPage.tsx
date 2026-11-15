import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Asset,
  AssetDetailResponse,
  AssetFindingsResponse,
  AssetRiskSummary,
  AssetWithKev,
  FindingStatus,
  InventoryHealth,
  MatchConfidence,
  getAsset,
  getAssetFindings,
  getAssetRiskSummary,
  getInventoryHealth,
  listAssets,
  patchAssetFindingStatus,
  setAssetTags,
} from "../api/assets";
import SourceBadge from "../components/shared/SourceBadge";
import "../Dashboard.css";
import "./AssetsPage.css";

/**
 * Month 2 Phase C: Asset inventory page.
 *
 * Lists assets with their preliminary KEV-match count and a drill-down
 * into per-asset installed software.
 */

function SummaryStat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div>
      <div className="assets-text-subtle assets-fs-12">{label}</div>
      <div style={{ color, fontSize: 22, fontWeight: 700, marginTop: 2 }}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}

function DiscoveredViaBadge({ via }: { via: Asset["discovered_via"] }) {
  const label =
    via === "csv_upload" ? "CSV" : via === "m365" ? "M365" : via === "agent" ? "Agent" : via;
  const color =
    via === "csv_upload"
      ? "#2563eb"
      : via === "m365"
        ? "#9333ea"
        : via === "agent"
          ? "#059669"
          : "#64748b";
  return (
    <span
      style={{
        background: `${color}22`,
        color,
        padding: "2px 8px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
      }}
    >
      {label}
    </span>
  );
}

const CONFIDENCE_META: Record<
  MatchConfidence,
  { label: string; color: string; deemphasized: boolean }
> = {
  high: { label: "High confidence", color: "var(--conf-high)", deemphasized: false },
  medium: { label: "Medium confidence", color: "var(--conf-medium)", deemphasized: false },
  low: { label: "Low confidence", color: "var(--conf-low)", deemphasized: true },
  needs_review: { label: "Needs review", color: "var(--conf-low)", deemphasized: true },
};

function ConfidenceChip({ confidence }: { confidence: MatchConfidence }) {
  const meta = CONFIDENCE_META[confidence] ?? CONFIDENCE_META.needs_review;
  return (
    <span
      style={{
        background: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
        color: meta.color,
        border: meta.deemphasized ? `1px dashed ${meta.color}` : "none",
        padding: "2px 8px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 700,
        whiteSpace: "nowrap",
      }}
      aria-label={
        meta.deemphasized
          ? `${meta.label} — unverified match, review before acting`
          : meta.label
      }
      title={
        meta.deemphasized
          ? "This match is unverified — review before acting on it."
          : "Version-aware match against the CVE's affected ranges."
      }
    >
      {meta.label}
    </span>
  );
}

const TIER_COLORS: Record<string, string> = {
  Critical: "var(--tier-critical)",
  High: "var(--tier-high)",
  Medium: "var(--tier-medium)",
  Low: "var(--tier-low)",
  "Needs Review": "var(--tier-review)",
};

function RiskTierChip({ tier }: { tier: string }) {
  const color = TIER_COLORS[tier] ?? "var(--tier-review)";
  return (
    <span
      style={{
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        color,
        padding: "2px 8px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 700,
        whiteSpace: "nowrap",
      }}
    >
      {tier}
    </span>
  );
}

const STATUS_LABELS: Record<FindingStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  fixed: "Fixed",
  accepted_risk: "Accepted risk",
  false_positive: "False positive",
};

export default function AssetsPage() {
  const { orgId } = useAuth();
  const [items, setItems] = useState<AssetWithKev[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hostname, setHostname] = useState("");
  const [vendorFilter, setVendorFilter] = useState<string | null>(null);
  const [kevOnly, setKevOnly] = useState(false);
  const [summary, setSummary] = useState<InventoryHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<AssetDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [findings, setFindings] = useState<AssetFindingsResponse | null>(null);
  const [findingsLoading, setFindingsLoading] = useState(false);
  const [findingsError, setFindingsError] = useState("");
  const [findingsRefreshing, setFindingsRefreshing] = useState(false);
  const [tagDraft, setTagDraft] = useState("");
  const [tagSaving, setTagSaving] = useState(false);
  const [findingActionId, setFindingActionId] = useState<number | null>(null);
  const [tagFilter, setTagFilter] = useState("");
  const [risk, setRisk] = useState<AssetRiskSummary | null>(null);
  const pageSize = 50;

  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError("");
    try {
      const data = await listAssets(orgId, {
        page,
        pageSize,
        hostname: hostname || undefined,
        vendor: vendorFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setLoadedOnce(true);
    }
  }, [orgId, page, hostname, vendorFilter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!orgId) return;
    getAssetRiskSummary(orgId, 5)
      .then(setRisk)
      .catch(() => setRisk(null));
  }, [orgId, items.length]);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    getInventoryHealth(orgId)
      .then((s) => {
        if (!cancelled) setSummary(s);
      })
      .catch(() => {
        /* summary is non-essential; keep silent */
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const openDetail = async (assetId: number) => {
    if (!orgId) return;
    setDetailLoading(true);
    setFindings(null);
    setFindingsLoading(true);
    setFindingsError("");
    setTagDraft("");
    try {
      const d = await getAsset(orgId, assetId);
      setDetail(d);
      setTagDraft((d.asset.tags ?? []).join(", "));
      try {
        setFindings(await getAssetFindings(orgId, assetId));
      } catch (e) {
        // Surface in the modal rather than the page-level banner (which renders
        // behind the overlay) so the "(—)" count isn't an unexplained dead-end.
        setFindingsError((e as Error).message);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
      setFindingsLoading(false);
    }
  };

  const refreshFindings = async () => {
    if (!orgId || !detail) return;
    setFindingsRefreshing(true);
    setFindingsError("");
    try {
      setFindings(await getAssetFindings(orgId, detail.asset.id, { refresh: true }));
    } catch (e) {
      setFindingsError((e as Error).message);
    } finally {
      setFindingsRefreshing(false);
    }
  };

  const saveTags = async () => {
    if (!orgId || !detail) return;
    setTagSaving(true);
    try {
      const tags = tagDraft
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const updated = await setAssetTags(orgId, detail.asset.id, tags);
      setDetail({ ...detail, asset: updated });
      setItems((prev) =>
        prev.map((r) =>
          r.asset.id === updated.id ? { ...r, asset: updated } : r,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTagSaving(false);
    }
  };

  const updateFindingStatus = async (
    findingId: number,
    status: FindingStatus,
  ) => {
    if (!orgId || !detail) return;
    setFindingActionId(findingId);
    setFindingsError("");
    try {
      const updated = await patchAssetFindingStatus(
        orgId,
        detail.asset.id,
        findingId,
        status,
      );
      // Trust the server's authoritative status, not the requested one.
      setFindings((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((m) =>
                m.finding_id === findingId ? { ...m, status: updated.status } : m,
              ),
            }
          : prev,
      );
    } catch (e) {
      setFindingsError((e as Error).message);
    } finally {
      setFindingActionId(null);
    }
  };

  const tagFilterLower = tagFilter.trim().toLowerCase();
  const visible = items
    .filter((r) => (kevOnly ? r.kev_match_count > 0 : true))
    .filter((r) =>
      tagFilterLower
        ? (r.asset.tags ?? []).some((t) => t.includes(tagFilterLower))
        : true,
    );
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  // Only badge data that has actually loaded: not before the first load, with
  // no org, while loading, or when the load failed.
  const showBadges = Boolean(orgId) && loadedOnce && !loading && !error;

  return (
    <div className="dashboard-page" style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h1>Assets</h1>
          {showBadges && (
            <SourceBadge datasetKey="assets_inventory" className="widget-source-badge" />
          )}
        </div>
        <Link to="/org/assets/upload">
          <button type="button">Upload CSV</button>
        </Link>
      </div>

      {summary && (
        <div className="assets-summary">
          <SummaryStat label="Assets" value={summary.assets_total} color="var(--accent)" />
          <SummaryStat
            label="With software"
            value={summary.assets_with_known_software}
            color="var(--accent)"
          />
          <SummaryStat
            label="KEV-matched"
            value={summary.assets_with_kev_match}
            color={summary.assets_with_kev_match > 0 ? "var(--color-critical)" : "var(--text-subtle)"}
          />
          <div>
            <div className="assets-text-subtle assets-fs-12">Last upload</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
              {summary.last_inventory_update
                ? new Date(summary.last_inventory_update).toLocaleString()
                : "—"}
            </div>
            {summary.last_source && (
              <div className="assets-text-subtle assets-fs-11" style={{ marginTop: 2 }}>
                via {summary.last_source}
              </div>
            )}
          </div>
        </div>
      )}

      {risk && risk.items.length > 0 && (
        <div className="assets-risk-panel">
          <div className="assets-risk-title">RISKIEST ASSETS</div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr className="assets-risk-head-row">
                <th style={{ padding: 4 }}>Asset</th>
                <th style={{ padding: 4 }}>Max CVSS</th>
                <th style={{ padding: 4 }}>EPSS %ile</th>
                <th style={{ padding: 4 }}>Risk score</th>
              </tr>
            </thead>
            <tbody>
              {risk.items.map((r) => (
                <tr key={r.asset_id} className="assets-risk-row">
                  <td style={{ padding: 4 }}>
                    <button
                      type="button"
                      onClick={() => openDetail(r.asset_id)}
                      className="assets-risk-link"
                    >
                      {r.hostname}
                    </button>
                    {r.in_kev && (
                      <span className="assets-kev-chip assets-kev-chip-sm">KEV</span>
                    )}
                  </td>
                  <td style={{ padding: 4 }}>{r.max_cvss?.toFixed(1) ?? "—"}</td>
                  <td style={{ padding: 4 }}>
                    {r.max_epss_percentile !== null
                      ? `${r.max_epss_percentile.toFixed(1)}`
                      : "—"}
                  </td>
                  <td style={{ padding: 4, fontWeight: 700 }}>
                    {r.risk_score.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="assets-risk-note">{risk.note}</div>
        </div>
      )}

      {summary && summary.top_vendors.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 6,
            alignItems: "center",
            flexWrap: "wrap",
            marginTop: 12,
          }}
        >
          <span className="assets-text-subtle assets-fs-12">Top vendors:</span>
          {summary.top_vendors.map((v) => {
            const active = vendorFilter === v.vendor;
            return (
              <button
                key={v.vendor}
                type="button"
                onClick={() => {
                  setPage(1);
                  setVendorFilter(active ? null : v.vendor);
                }}
                className={
                  active ? "assets-vendor-chip assets-vendor-chip-active" : "assets-vendor-chip"
                }
              >
                {v.vendor} · {v.asset_count}
              </button>
            );
          })}
          {vendorFilter && (
            <button
              type="button"
              onClick={() => {
                setPage(1);
                setVendorFilter(null);
              }}
              className="assets-clear-filter"
            >
              Clear filter ✕
            </button>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 12, alignItems: "center", margin: "16px 0" }}>
        <input
          type="text"
          placeholder="Search hostname"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setPage(1);
              load();
            }
          }}
          style={{ padding: 6, width: 260 }}
        />
        <label style={{ fontSize: 14 }}>
          <input
            type="checkbox"
            checked={kevOnly}
            onChange={(e) => setKevOnly(e.target.checked)}
          />{" "}
          KEV matches only
        </label>
        <input
          type="text"
          placeholder="Filter by tag"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          style={{ padding: 6, width: 160 }}
        />
        <span className="assets-text-subtle" style={{ marginLeft: "auto", fontSize: 13 }}>
          {total} total · page {page} / {totalPages}
        </span>
        {showBadges && visible.length > 0 && (
          <SourceBadge datasetKey="asset_kev_matches" className="widget-source-badge" />
        )}
      </div>

      {error && (
        <div className="assets-error">{error}</div>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : visible.length === 0 ? (
        <p>
          No assets yet. <Link to="/org/assets/upload">Upload a CSV</Link> to populate this list.
        </p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr className="assets-head-row">
              <th style={{ padding: 8 }}>Hostname</th>
              <th style={{ padding: 8 }}>OS</th>
              <th style={{ padding: 8 }}>IP</th>
              <th style={{ padding: 8 }}>Source</th>
              <th style={{ padding: 8 }}>KEV matches</th>
              <th style={{ padding: 8 }}>Tags</th>
              <th style={{ padding: 8 }}>Last seen</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visible.map(({ asset, kev_match_count }) => (
              <tr key={asset.id} className="assets-row">
                <td style={{ padding: 8 }}>
                  <strong>{asset.hostname}</strong>
                </td>
                <td style={{ padding: 8 }}>
                  {asset.os_name} {asset.os_version}
                </td>
                <td style={{ padding: 8 }}>{asset.ip_address ?? "—"}</td>
                <td style={{ padding: 8 }}>
                  <DiscoveredViaBadge via={asset.discovered_via} />
                </td>
                <td style={{ padding: 8 }}>
                  {kev_match_count > 0 ? (
                    <span style={{ color: "var(--color-critical)", fontWeight: 600 }}>
                      {kev_match_count}
                    </span>
                  ) : (
                    <span className="assets-text-subtle">0</span>
                  )}
                </td>
                <td style={{ padding: 8 }}>
                  {(asset.tags ?? []).length === 0 ? (
                    <span className="assets-text-subtle assets-fs-11">—</span>
                  ) : (
                    <span style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {(asset.tags ?? []).map((t) => (
                        <span key={t} className="assets-tag">
                          {t}
                        </span>
                      ))}
                    </span>
                  )}
                </td>
                <td className="assets-text-secondary assets-fs-12" style={{ padding: 8 }}>
                  {new Date(asset.last_seen).toLocaleDateString()}
                </td>
                <td style={{ padding: 8 }}>
                  <button type="button" onClick={() => openDetail(asset.id)}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
          ← Prev
        </button>
        <button
          type="button"
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages}
        >
          Next →
        </button>
      </div>

      {detail && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
          onClick={() => setDetail(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="assets-modal-card"
          >
            <h2 style={{ marginTop: 0 }}>{detail.asset.hostname}</h2>
            <p>
              {detail.asset.os_name} {detail.asset.os_version} · {detail.asset.ip_address ?? "no IP"}{" "}
              · <DiscoveredViaBadge via={detail.asset.discovered_via} />
            </p>
            <div className="assets-tag-editor">
              <div className="assets-text-subtle assets-fs-12" style={{ marginBottom: 4 }}>
                Tags (comma-separated)
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="text"
                  value={tagDraft}
                  onChange={(e) => setTagDraft(e.target.value)}
                  placeholder="e.g. production, pci-zone, executive-laptop"
                  style={{ flex: 1, padding: 6 }}
                />
                <button type="button" onClick={saveTags} disabled={tagSaving}>
                  {tagSaving ? "Saving…" : "Save tags"}
                </button>
              </div>
            </div>
            <div
              style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}
            >
              <h3 style={{ marginBottom: 0 }}>
                CVE matches{" "}
                {findingsLoading ? "(loading…)" : findings ? `(${findings.total})` : "(—)"}
              </h3>
              <button
                type="button"
                onClick={refreshFindings}
                disabled={findingsLoading || findingsRefreshing}
                title="Re-run the version-aware matcher against this asset's software"
                className="assets-outline-btn assets-text-secondary"
              >
                {findingsRefreshing ? "Recomputing…" : "Recompute"}
              </button>
            </div>
            {findingsError && (
              <p
                role="alert"
                className="assets-error-inline"
              >
                {findingsError}
              </p>
            )}
            {findings && findings.items.length === 0 && !findingsLoading && (
              <p className="assets-text-subtle" style={{ fontSize: 13 }}>
                No CVEs match this asset's software.
              </p>
            )}
            {findings && findings.items.length > 0 && (
              <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 12 }}>
                <thead>
                  <tr className="assets-findings-head-row">
                    <th style={{ padding: 6 }}>CVE</th>
                    <th style={{ padding: 6 }}>Software</th>
                    <th style={{ padding: 6 }}>Confidence</th>
                    <th style={{ padding: 6 }}>Risk</th>
                    <th style={{ padding: 6 }}>CVSS</th>
                    <th style={{ padding: 6 }}>EPSS</th>
                    <th style={{ padding: 6 }}>KEV</th>
                    <th style={{ padding: 6 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.items.map((m) => {
                    const deemphasized = CONFIDENCE_META[m.match_confidence]?.deemphasized;
                    const isFalsePositive = m.status === "false_positive";
                    return (
                      <tr
                        key={m.finding_id}
                        className="assets-row"
                        style={{
                          opacity: deemphasized || isFalsePositive ? 0.55 : 1,
                          textDecoration: isFalsePositive ? "line-through" : "none",
                        }}
                      >
                        <td style={{ padding: 6, fontFamily: "monospace" }}>{m.cve_id}</td>
                        <td style={{ padding: 6 }}>
                          {m.vendor} {m.product}
                          {m.version ? ` ${m.version}` : ""}
                        </td>
                        <td style={{ padding: 6 }}>
                          <ConfidenceChip confidence={m.match_confidence} />
                        </td>
                        <td style={{ padding: 6 }}>
                          <RiskTierChip tier={m.risk_tier} />
                        </td>
                        <td style={{ padding: 6 }}>{m.cvss_score?.toFixed(1) ?? "—"}</td>
                        <td style={{ padding: 6 }}>
                          {m.epss_score !== null
                            ? `${(m.epss_score * 100).toFixed(1)}%`
                            : "—"}
                        </td>
                        <td style={{ padding: 6 }}>
                          {m.in_kev && (
                            <span className="assets-kev-chip assets-kev-chip-md">KEV</span>
                          )}
                        </td>
                        <td style={{ padding: 6, whiteSpace: "nowrap" }}>
                          <span
                            className="assets-text-secondary assets-fs-12"
                            aria-label={
                              isFalsePositive ? "Status: false positive (dismissed)" : undefined
                            }
                          >
                            {STATUS_LABELS[m.status] ?? m.status}
                          </span>
                          {!isFalsePositive && (
                            <button
                              type="button"
                              onClick={() =>
                                updateFindingStatus(m.finding_id, "false_positive")
                              }
                              disabled={findingActionId === m.finding_id}
                              title="Flag this match as a false positive"
                              className="assets-outline-btn assets-text-subtle"
                              style={{ marginLeft: 8, padding: "2px 6px" }}
                            >
                              {findingActionId === m.finding_id
                                ? "…"
                                : "Report false positive"}
                            </button>
                          )}
                          {isFalsePositive && (
                            <button
                              type="button"
                              onClick={() => updateFindingStatus(m.finding_id, "open")}
                              disabled={findingActionId === m.finding_id}
                              title="Undo false-positive flag"
                              className="assets-link-btn"
                              style={{ marginLeft: 8 }}
                            >
                              Undo
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            {findings &&
              findings.items.some((m) => m.remediation_summary) && (
                <div className="assets-remediation">
                  <div className="assets-remediation-title">Remediation</div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                    {findings.items
                      .filter((m) => m.remediation_summary)
                      .map((m) => (
                        <li key={m.finding_id} style={{ marginBottom: 4 }}>
                          <span style={{ fontFamily: "monospace" }}>{m.cve_id}</span>:{" "}
                          {m.remediation_summary}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            {findings && (
              <p className="assets-text-subtle assets-note">
                {findings.note}
              </p>
            )}

            <h3>Software ({detail.software.length})</h3>
            {detail.software.length === 0 ? (
              <p>No software records — the CSV row had no vendor/product columns.</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr className="assets-head-row">
                    <th style={{ padding: 6 }}>Vendor</th>
                    <th style={{ padding: 6 }}>Product</th>
                    <th style={{ padding: 6 }}>Version</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.software.map((s) => (
                    <tr key={s.id} className="assets-row">
                      <td style={{ padding: 6 }}>{s.vendor}</td>
                      <td style={{ padding: 6 }}>{s.product}</td>
                      <td style={{ padding: 6 }}>{s.version ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {detail.services?.length > 0 && (
              <>
                <h3 style={{ marginTop: 20 }}>
                  Running services ({detail.services.length})
                </h3>
                <p className="assets-text-subtle assets-note">
                  Latest snapshot from the host scanner.
                </p>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr className="assets-head-row">
                      <th style={{ padding: 6 }}>Service</th>
                      <th style={{ padding: 6 }}>State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.services.map((svc) => (
                      <tr key={svc.name} className="assets-row">
                        <td style={{ padding: 6 }}>{svc.name}</td>
                        <td style={{ padding: 6 }}>{svc.state ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {detail.listening_ports?.length > 0 && (
              <>
                <h3 style={{ marginTop: 20 }}>
                  Listening ports ({detail.listening_ports.length})
                </h3>
                <p className="assets-text-subtle assets-note">
                  Collected only when the scanner is run with --include-ports.
                </p>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr className="assets-head-row">
                      <th style={{ padding: 6 }}>Port</th>
                      <th style={{ padding: 6 }}>Protocol</th>
                      <th style={{ padding: 6 }}>Process</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.listening_ports.map((p) => (
                      <tr key={`${p.protocol}/${p.port}`} className="assets-row">
                        <td style={{ padding: 6 }}>{p.port}</td>
                        <td style={{ padding: 6 }}>{p.protocol}</td>
                        <td style={{ padding: 6 }}>{p.process ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <div style={{ marginTop: 16 }}>
              <button type="button" onClick={() => setDetail(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {detailLoading && <p>Loading detail…</p>}
    </div>
  );
}
