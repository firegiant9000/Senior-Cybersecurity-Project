import { useState, useEffect, useCallback } from "react";
import { OrgDomain, listDomains, addDomain, deleteDomain } from "../../api/domains";
import type { SectionProps } from "./types";

const domainPageSize = 20;

// Stays mounted while collapsed so its state survives; it renders nothing until `open`.
export default function DomainsSection({
  orgId,
  onChanged,
  open,
}: SectionProps & { open: boolean }) {
  const [domains, setDomains] = useState<OrgDomain[]>([]);
  const [domainTotal, setDomainTotal] = useState(0);
  const [domainPage, setDomainPage] = useState(1);
  const [domainLoading, setDomainLoading] = useState(false);
  const [domainError, setDomainError] = useState("");
  const [domainMsg, setDomainMsg] = useState("");
  const [newDomain, setNewDomain] = useState("");

  const loadDomains = useCallback(async (id: number, page: number) => {
    setDomainLoading(true);
    setDomainError("");
    try {
      const data = await listDomains(id, page, domainPageSize);
      setDomains(data.items);
      setDomainTotal(data.total);
    } catch {
      setDomainError("Failed to load domains");
    } finally {
      setDomainLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDomains(orgId, domainPage);
  }, [orgId, domainPage, loadDomains]);

  const handleAddDomain = async () => {
    if (!newDomain.trim()) return;
    setDomainError("");
    const cleaned = newDomain
      .trim()
      .replace(/^https?:\/\//i, "")
      .replace(/\/.*$/, "")
      .toLowerCase()
      .replace(/\.$/, "");
    const isDupe = domains.some((d) => d.domain_name.toLowerCase() === cleaned);
    if (isDupe) {
      setDomainError("This domain is already registered.");
      return;
    }
    try {
      await addDomain(orgId, cleaned);
      setNewDomain("");
      setDomainMsg("Domain added");
      setDomainPage(1);
      loadDomains(orgId, 1);
      onChanged();
    } catch (err) {
      setDomainError(
        err instanceof Error ? err.message : "Failed to add domain",
      );
    }
  };

  const handleDeleteDomain = async (domainId: number) => {
    setDomainError("");
    try {
      await deleteDomain(orgId, domainId);
      setDomainPage(1);
      loadDomains(orgId, 1);
      onChanged();
    } catch {
      setDomainError("Failed to remove domain");
    }
  };

  if (!open) return null;

  return (
    <div className="section-accordion-body">
      {domainMsg && <div className="settings-action-msg">{domainMsg}</div>}
      {domainError && (
        <div
          className="settings-error"
          style={{
            whiteSpace: "pre-line",
            marginBottom: "0.75rem",
          }}
        >
          {domainError}
        </div>
      )}

      <div className="vendor-add-form">
        <div className="vendor-input-wrapper">
          <input
            type="text"
            placeholder="example.com"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
          />
        </div>
        <button
          className="action-btn"
          onClick={handleAddDomain}
          disabled={!newDomain.trim()}
        >
          Add Domain
        </button>
      </div>

      {domainLoading ? (
        <p className="settings-loading">Loading domains...</p>
      ) : domains.length === 0 ? (
        <p className="vendor-empty">No domains added yet.</p>
      ) : (
        <>
          <table className="vendor-table">
            <thead>
              <tr>
                <th>Domain</th>
                <th>Added</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {domains.map((d) => (
                <tr key={d.id}>
                  <td>{d.domain_name}</td>
                  <td>{new Date(d.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="vendor-delete-btn"
                      onClick={() => handleDeleteDomain(d.id)}
                      title="Remove"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {domainTotal > domainPageSize && (
            <div className="vendor-pagination">
              <button
                className="action-btn"
                disabled={domainPage <= 1}
                onClick={() => setDomainPage((p) => p - 1)}
              >
                Previous
              </button>
              <span className="vendor-page-info">
                Page {domainPage} of {Math.ceil(domainTotal / domainPageSize)}
              </span>
              <button
                className="action-btn"
                disabled={domainPage >= Math.ceil(domainTotal / domainPageSize)}
                onClick={() => setDomainPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
