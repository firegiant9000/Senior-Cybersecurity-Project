import { useState, useEffect, useCallback, useRef } from "react";
import {
  OrgVendor,
  OrgVendorImportPreviewResponse,
  VendorSuggestion,
  listVendors,
  createVendor,
  deleteVendor,
  importVendorsCsv,
  previewVendorsCsv,
  suggestVendors,
  autocompleteVendors,
} from "../../api/vendors";
import type { SectionProps } from "./types";

const vendorPageSize = 20;

export default function TechnologySection({
  orgId,
  onChanged,
  reloadKey = 0,
}: SectionProps & { reloadKey?: number }) {
  const [vendors, setVendors] = useState<OrgVendor[]>([]);
  const [vendorTotal, setVendorTotal] = useState(0);
  const [vendorPage, setVendorPage] = useState(1);
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorError, setVendorError] = useState("");
  const [vendorMsg, setVendorMsg] = useState("");
  const [newVendor, setNewVendor] = useState("");
  const [newProduct, setNewProduct] = useState("");
  const [vendorSuggestions, setVendorSuggestions] = useState<VendorSuggestion[]>([]);
  const [productSuggestions, setProductSuggestions] = useState<string[]>([]);
  const [showVendorSuggestions, setShowVendorSuggestions] = useState(false);
  const [showProductSuggestions, setShowProductSuggestions] = useState(false);
  const vendorInputRef = useRef<HTMLInputElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // CSV preview state
  const [csvPreview, setCsvPreview] = useState<OrgVendorImportPreviewResponse | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvPreviewing, setCsvPreviewing] = useState(false);

  // A parent-driven reload (e.g. cloud providers synced into vendors) returns to page 1.
  // Adjusting state during render means the load effect below runs once, on page 1.
  const [seenReloadKey, setSeenReloadKey] = useState(reloadKey);
  if (seenReloadKey !== reloadKey) {
    setSeenReloadKey(reloadKey);
    setVendorPage(1);
  }

  const loadVendors = useCallback(
    async (id: number, page: number) => {
      setVendorLoading(true);
      setVendorError("");
      try {
        const data = await listVendors(id, page, vendorPageSize);
        setVendors(data.items);
        setVendorTotal(data.total);
      } catch {
        setVendorError("Failed to load technology stack");
      } finally {
        setVendorLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadVendors(orgId, vendorPage);
  }, [orgId, vendorPage, reloadKey, loadVendors]);

  const handleAddVendor = async () => {
    if (!newVendor.trim()) return;
    setVendorError("");
    const normalizedNew = newVendor.trim().replace(/\s+/g, " ").toLowerCase();
    const normalizedProd = newProduct.trim().replace(/\s+/g, " ").toLowerCase();
    const isDupe = vendors.some(
      (v) =>
        v.vendor_name.toLowerCase() === normalizedNew &&
        v.product_name.toLowerCase() === normalizedProd,
    );
    if (isDupe) {
      setVendorError("A vendor with this name already exists in your stack.");
      return;
    }
    try {
      await createVendor(orgId, newVendor.trim(), newProduct.trim());
      setNewVendor("");
      setNewProduct("");
      setVendorMsg("Vendor added");
      setVendorPage(1);
      loadVendors(orgId, 1);
      onChanged();
    } catch (err) {
      setVendorError(
        err instanceof Error ? err.message : "Failed to add vendor",
      );
    }
  };

  const handleDeleteVendor = async (vendorId: number) => {
    setVendorError("");
    try {
      await deleteVendor(orgId, vendorId);
      setVendorPage(1);
      loadVendors(orgId, 1);
      onChanged();
    } catch {
      setVendorError("Failed to remove vendor");
    }
  };

  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setVendorError("");
    setVendorMsg("");
    setCsvPreviewing(true);
    try {
      const preview = await previewVendorsCsv(orgId, file);
      setCsvPreview(preview);
      setCsvFile(file);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "CSV preview failed");
    } finally {
      setCsvPreviewing(false);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleCsvConfirm = async () => {
    if (!csvFile) return;
    setVendorError("");
    setVendorMsg("");
    try {
      const result = await importVendorsCsv(orgId, csvFile);
      const parts: string[] = [];
      if (result.imported) parts.push(`${result.imported} imported`);
      if (result.skipped) parts.push(`${result.skipped} duplicates skipped`);
      if (result.errors.length) parts.push(`${result.errors.length} errors`);
      if (!result.imported && !result.skipped && !result.errors.length) {
        setVendorError("CSV contained no valid vendor rows");
      } else {
        setVendorMsg(parts.join(", "));
      }
      if (result.errors.length) {
        setVendorError(result.errors.slice(0, 5).join("\n"));
      }
      loadVendors(orgId, 1);
      setVendorPage(1);
      onChanged();
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "CSV import failed");
    } finally {
      setCsvPreview(null);
      setCsvFile(null);
    }
  };

  const handleCsvCancel = () => {
    setCsvPreview(null);
    setCsvFile(null);
  };

  // Debounced typeahead for vendor name — uses fuzzy suggest endpoint with confidence scores
  useEffect(() => {
    if (newVendor.length < 2) {
      setVendorSuggestions([]);
      setShowVendorSuggestions(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await suggestVendors(newVendor);
        if (!cancelled) {
          setVendorSuggestions(results);
          setShowVendorSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) {
          setVendorSuggestions([]);
          setShowVendorSuggestions(false);
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [newVendor]);

  // Debounced autocomplete for product name
  useEffect(() => {
    if (newProduct.length < 2) {
      setProductSuggestions([]);
      setShowProductSuggestions(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(
          newProduct,
          "product",
          newVendor || undefined,
        );
        if (!cancelled) {
          setProductSuggestions(results);
          setShowProductSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) {
          setProductSuggestions([]);
          setShowProductSuggestions(false);
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [newProduct, newVendor]);

  return (
    <div className="section-accordion-body">
      {vendorMsg && <div className="settings-action-msg">{vendorMsg}</div>}
      {vendorError && (
        <div
          className="settings-error"
          style={{
            whiteSpace: "pre-line",
            marginBottom: "0.75rem",
          }}
        >
          {vendorError}
        </div>
      )}

      <div className="vendor-add-form">
        <div className="vendor-input-wrapper">
          <input
            ref={vendorInputRef}
            type="text"
            placeholder="Vendor name"
            value={newVendor}
            onChange={(e) => setNewVendor(e.target.value)}
            onFocus={() =>
              vendorSuggestions.length > 0 && setShowVendorSuggestions(true)
            }
            onBlur={() =>
              setTimeout(() => setShowVendorSuggestions(false), 200)
            }
          />
          {showVendorSuggestions && (
            <ul className="autocomplete-dropdown">
              {vendorSuggestions.map((s) => (
                <li
                  key={s.vendor_name}
                  onMouseDown={() => {
                    setNewVendor(s.vendor_name);
                    setShowVendorSuggestions(false);
                  }}
                  title={`${Math.round(s.score * 100)}% match`}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}
                >
                  <span>{s.vendor_name}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>
                    {Math.round(s.score * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="vendor-input-wrapper">
          <input
            ref={productInputRef}
            type="text"
            placeholder="Product name (optional)"
            value={newProduct}
            onChange={(e) => setNewProduct(e.target.value)}
            onFocus={() =>
              productSuggestions.length > 0 && setShowProductSuggestions(true)
            }
            onBlur={() =>
              setTimeout(() => setShowProductSuggestions(false), 200)
            }
          />
          {showProductSuggestions && (
            <ul className="autocomplete-dropdown">
              {productSuggestions.map((s) => (
                <li
                  key={s}
                  onMouseDown={() => {
                    setNewProduct(s);
                    setShowProductSuggestions(false);
                  }}
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          className="action-btn"
          onClick={handleAddVendor}
          disabled={!newVendor.trim()}
        >
          Add
        </button>
      </div>

      <div className="vendor-import-row">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={handleCsvImport}
        />
        <button
          className="action-btn"
          disabled={csvPreviewing}
          onClick={() => fileInputRef.current?.click()}
        >
          {csvPreviewing ? "Previewing…" : "Import CSV"}
        </button>
        <span className="vendor-import-hint">
          CSV with vendor_name column (max 500 rows)
        </span>
      </div>

      {csvPreview && (
        <div className="csv-preview-panel">
          <p className="csv-preview-summary">
            <strong>CSV preview:</strong> {csvPreview.would_import} row
            {csvPreview.would_import !== 1 ? "s" : ""} to import
            {csvPreview.would_skip > 0
              ? `, ${csvPreview.would_skip} in-file duplicate${csvPreview.would_skip !== 1 ? "s" : ""} skipped`
              : ""}
            {csvPreview.errors.length > 0
              ? `, ${csvPreview.errors.length} error${csvPreview.errors.length !== 1 ? "s" : ""}`
              : ""}
          </p>
          {csvPreview.errors.length > 0 && (
            <ul className="csv-preview-errors">
              {csvPreview.errors.slice(0, 5).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
              {csvPreview.errors.length > 5 && (
                <li>…and {csvPreview.errors.length - 5} more</li>
              )}
            </ul>
          )}
          <div className="csv-preview-actions">
            <button
              className="action-btn"
              disabled={csvPreview.would_import === 0}
              onClick={handleCsvConfirm}
            >
              Confirm Import
            </button>
            <button className="action-btn-secondary" onClick={handleCsvCancel}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {vendorLoading ? (
        <p className="settings-loading">Loading vendors...</p>
      ) : vendors.length === 0 ? (
        <p className="vendor-empty">
          No vendors added yet. Add your first vendor above or import a CSV.
        </p>
      ) : (
        <>
          <table className="vendor-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Product</th>
                <th>Added</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.id}>
                  <td>
                    {v.vendor_name}
                    <span className="matched-count-badge">
                      {v.matched_kev_count} KEV
                    </span>
                  </td>
                  <td>{v.product_name || "-"}</td>
                  <td>{new Date(v.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="vendor-delete-btn"
                      onClick={() => handleDeleteVendor(v.id)}
                      title="Remove"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {vendorTotal > vendorPageSize && (
            <div className="vendor-pagination">
              <button
                className="action-btn"
                disabled={vendorPage <= 1}
                onClick={() => setVendorPage((p) => p - 1)}
              >
                Previous
              </button>
              <span className="vendor-page-info">
                Page {vendorPage} of {Math.ceil(vendorTotal / vendorPageSize)}
              </span>
              <button
                className="action-btn"
                disabled={vendorPage >= Math.ceil(vendorTotal / vendorPageSize)}
                onClick={() => setVendorPage((p) => p + 1)}
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
