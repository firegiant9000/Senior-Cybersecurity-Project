import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { sendEmailVerification, sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import {
  OrgVendor,
  listVendors,
  createVendor,
  deleteVendor,
  importVendorsCsv,
  autocompleteVendors,
} from "../api/vendors";
import "./SettingsPage.css";

interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  auth_provider: string;
  created_at: string;
  org_id: number | null;
  org_role: string | null;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  // Vendor / Tech Stack state
  const [vendors, setVendors] = useState<OrgVendor[]>([]);
  const [vendorTotal, setVendorTotal] = useState(0);
  const [vendorPage, setVendorPage] = useState(1);
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorError, setVendorError] = useState("");
  const [vendorMsg, setVendorMsg] = useState("");
  const [newVendor, setNewVendor] = useState("");
  const [newProduct, setNewProduct] = useState("");
  const [vendorSuggestions, setVendorSuggestions] = useState<string[]>([]);
  const [productSuggestions, setProductSuggestions] = useState<string[]>([]);
  const [showVendorSuggestions, setShowVendorSuggestions] = useState(false);
  const [showProductSuggestions, setShowProductSuggestions] = useState(false);
  const vendorInputRef = useRef<HTMLInputElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const vendorPageSize = 20;

  const loadVendors = useCallback(async (orgId: number, page: number) => {
    setVendorLoading(true);
    setVendorError("");
    try {
      const data = await listVendors(orgId, page, vendorPageSize);
      setVendors(data.items);
      setVendorTotal(data.total);
    } catch {
      setVendorError("Failed to load technology stack");
    } finally {
      setVendorLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.org_id) {
      loadVendors(profile.org_id, vendorPage);
    }
  }, [profile?.org_id, vendorPage, loadVendors]);

  const handleAddVendor = async () => {
    if (!profile?.org_id || !newVendor.trim()) return;
    setVendorError("");
    try {
      await createVendor(profile.org_id, newVendor.trim(), newProduct.trim());
      setNewVendor("");
      setNewProduct("");
      setVendorMsg("Vendor added");
      setVendorPage(1);
      loadVendors(profile.org_id, 1);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "Failed to add vendor");
    }
  };

  const handleDeleteVendor = async (vendorId: number) => {
    if (!profile?.org_id) return;
    setVendorError("");
    try {
      await deleteVendor(profile.org_id, vendorId);
      setVendorPage(1);
      loadVendors(profile.org_id, 1);
    } catch {
      setVendorError("Failed to remove vendor");
    }
  };

  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !profile?.org_id) return;
    setVendorError("");
    setVendorMsg("");
    try {
      const result = await importVendorsCsv(profile.org_id, file);
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
      loadVendors(profile.org_id, 1);
      setVendorPage(1);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "CSV import failed");
    }
    // Reset file input so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Debounced autocomplete for vendor name
  useEffect(() => {
    if (newVendor.length < 2) { setVendorSuggestions([]); setShowVendorSuggestions(false); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(newVendor, "vendor");
        if (!cancelled) {
          setVendorSuggestions(results);
          setShowVendorSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) { setVendorSuggestions([]); setShowVendorSuggestions(false); }
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [newVendor]);

  // Debounced autocomplete for product name
  useEffect(() => {
    if (newProduct.length < 2) { setProductSuggestions([]); setShowProductSuggestions(false); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(newProduct, "product", newVendor || undefined);
        if (!cancelled) {
          setProductSuggestions(results);
          setShowProductSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) { setProductSuggestions([]); setShowProductSuggestions(false); }
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [newProduct, newVendor]);

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data: UserProfile = await resp.json();
        if (!cancelled) setProfile(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadProfile();
    return () => { cancelled = true; };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleResendVerification = async () => {
    setActionMsg("");
    try {
      if (auth.currentUser) {
        await sendEmailVerification(auth.currentUser);
        setActionMsg("Verification email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send verification email. Try again later.");
    }
  };

  const handlePasswordReset = async () => {
    setActionMsg("");
    try {
      if (user?.email) {
        await sendPasswordResetEmail(auth, user.email);
        setActionMsg("Password reset email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send password reset email. Try again later.");
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-card">
        <div className="settings-header">
          <h1>Account Settings</h1>
          <button className="back-btn" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
        </div>

        {loading && <p className="settings-loading">Loading profile...</p>}
        {error && <div className="settings-error">{error}</div>}

        {!loading && !error && profile && (
          <div className="settings-sections">
            <section className="settings-section">
              <h2>Profile</h2>
              <div className="settings-field">
                <label>Email</label>
                <span>{profile.email}</span>
              </div>
              <div className="settings-field">
                <label>Role</label>
                <span className="role-badge">{profile.role}</span>
              </div>
              <div className="settings-field">
                <label>Auth Provider</label>
                <span>{profile.auth_provider}</span>
              </div>
              <div className="settings-field">
                <label>Account Created</label>
                <span>{new Date(profile.created_at).toLocaleDateString()}</span>
              </div>
              <div className="settings-field">
                <label>Status</label>
                <span className={`status-badge ${profile.is_active ? "active" : "inactive"}`}>
                  {profile.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Firebase Account</h2>
              <div className="settings-field">
                <label>Firebase UID</label>
                <span className="uid-text">{user?.uid}</span>
              </div>
              <div className="settings-field">
                <label>Email Verified</label>
                <span className={`status-badge ${user?.emailVerified ? "active" : "inactive"}`}>
                  {user?.emailVerified ? "Yes" : "No"}
                </span>
              </div>
              <div className="settings-field">
                <label>Last Sign-In</label>
                <span>{user?.metadata.lastSignInTime ?? "Unknown"}</span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Actions</h2>
              {actionMsg && <div className="settings-action-msg">{actionMsg}</div>}
              <div className="settings-actions">
                {!user?.emailVerified && (
                  <button className="action-btn" onClick={handleResendVerification}>
                    Resend Verification Email
                  </button>
                )}
                <button className="action-btn" onClick={handlePasswordReset}>
                  Reset Password
                </button>
                <button className="logout-btn" onClick={handleLogout}>
                  Log Out
                </button>
              </div>
            </section>

            {profile.org_id && (
              <section className="settings-section">
                <h2>Your Technology Stack</h2>
                <p className="tech-stack-description">
                  Track the vendors and products your organization uses. We'll highlight relevant vulnerabilities from the KEV catalog.
                </p>

                {vendorMsg && <div className="settings-action-msg">{vendorMsg}</div>}
                {vendorError && <div className="settings-error" style={{ whiteSpace: "pre-line", marginBottom: "0.75rem" }}>{vendorError}</div>}

                {/* Add vendor form */}
                <div className="vendor-add-form">
                  <div className="vendor-input-wrapper">
                    <input
                      ref={vendorInputRef}
                      type="text"
                      placeholder="Vendor name"
                      value={newVendor}
                      onChange={(e) => setNewVendor(e.target.value)}
                      onFocus={() => vendorSuggestions.length > 0 && setShowVendorSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowVendorSuggestions(false), 200)}
                    />
                    {showVendorSuggestions && (
                      <ul className="autocomplete-dropdown">
                        {vendorSuggestions.map((s) => (
                          <li key={s} onMouseDown={() => { setNewVendor(s); setShowVendorSuggestions(false); }}>{s}</li>
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
                      onFocus={() => productSuggestions.length > 0 && setShowProductSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowProductSuggestions(false), 200)}
                    />
                    {showProductSuggestions && (
                      <ul className="autocomplete-dropdown">
                        {productSuggestions.map((s) => (
                          <li key={s} onMouseDown={() => { setNewProduct(s); setShowProductSuggestions(false); }}>{s}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <button className="action-btn" onClick={handleAddVendor} disabled={!newVendor.trim()}>
                    Add
                  </button>
                </div>

                {/* CSV import */}
                <div className="vendor-import-row">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    style={{ display: "none" }}
                    onChange={handleCsvImport}
                  />
                  <button className="action-btn" onClick={() => fileInputRef.current?.click()}>
                    Import CSV
                  </button>
                  <span className="vendor-import-hint">CSV with vendor_name column (max 500 rows)</span>
                </div>

                {/* Vendor table */}
                {vendorLoading ? (
                  <p className="settings-loading">Loading vendors...</p>
                ) : vendors.length === 0 ? (
                  <p className="vendor-empty">No vendors added yet. Add your first vendor above or import a CSV.</p>
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
                            <td>{v.vendor_name}</td>
                            <td>{v.product_name || "-"}</td>
                            <td>{new Date(v.created_at).toLocaleDateString()}</td>
                            <td>
                              <button className="vendor-delete-btn" onClick={() => handleDeleteVendor(v.id)} title="Remove">
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
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
