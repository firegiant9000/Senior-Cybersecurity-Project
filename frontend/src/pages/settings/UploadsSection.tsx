import { useState, useEffect, useCallback, useRef } from "react";
import {
  OrgUpload,
  listUploads,
  uploadFile,
  deleteUpload,
  downloadUpload,
} from "../../api/uploads";
import type { SectionProps } from "./types";

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// Stays mounted while collapsed so its state survives; it renders nothing until `open`.
export default function UploadsSection({
  orgId,
  onChanged,
  open,
}: SectionProps & { open: boolean }) {
  const [uploads, setUploads] = useState<OrgUpload[]>([]);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [uploadPage, setUploadPage] = useState(1);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const uploadFileInputRef = useRef<HTMLInputElement>(null);

  const loadUploads = useCallback(async (id: number, page: number) => {
    setUploadLoading(true);
    setUploadError("");
    try {
      const data = await listUploads(id, page);
      setUploads(data.items);
      setUploadTotal(data.total);
    } catch {
      setUploadError("Failed to load uploads");
    } finally {
      setUploadLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUploads(orgId, uploadPage);
  }, [orgId, uploadPage, loadUploads]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError("");
    setUploadMsg("");
    try {
      await uploadFile(orgId, file);
      setUploadMsg(`"${file.name}" uploaded successfully`);
      loadUploads(orgId, 1);
      setUploadPage(1);
      onChanged();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    }
    if (uploadFileInputRef.current) uploadFileInputRef.current.value = "";
  };

  const handleDeleteUpload = async (uploadId: number) => {
    setUploadError("");
    try {
      await deleteUpload(orgId, uploadId);
      setUploadPage(1);
      loadUploads(orgId, 1);
      onChanged();
    } catch {
      setUploadError("Failed to delete upload");
    }
  };

  const handleDownloadUpload = async (uploadId: number, filename: string) => {
    try {
      await downloadUpload(orgId, uploadId, filename);
    } catch {
      setUploadError("Failed to download file");
    }
  };

  if (!open) return null;

  return (
    <div className="section-accordion-body">
      {uploadMsg && <div className="settings-action-msg">{uploadMsg}</div>}
      {uploadError && (
        <div
          className="settings-error"
          style={{
            whiteSpace: "pre-line",
            marginBottom: "0.75rem",
          }}
        >
          {uploadError}
        </div>
      )}

      <div className="vendor-import-row">
        <input
          ref={uploadFileInputRef}
          type="file"
          accept=".csv,.pdf,.txt,.json"
          style={{ display: "none" }}
          onChange={handleFileUpload}
        />
        <button
          className="action-btn"
          onClick={() => uploadFileInputRef.current?.click()}
        >
          Upload File
        </button>
        <span className="vendor-import-hint">
          Accepted: CSV, PDF, TXT, JSON (max 10 MB)
        </span>
      </div>

      {uploadLoading ? (
        <p className="settings-loading">Loading uploads...</p>
      ) : uploads.length === 0 ? (
        <p className="vendor-empty">No files uploaded yet.</p>
      ) : (
        <>
          <table className="vendor-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((u) => (
                <tr key={u.id}>
                  <td>
                    <button
                      className="vendor-delete-btn"
                      style={{
                        color: "#1565c0",
                        textDecoration: "underline",
                        cursor: "pointer",
                        background: "none",
                        border: "none",
                        font: "inherit",
                      }}
                      onClick={() =>
                        handleDownloadUpload(u.id, u.original_filename)
                      }
                      title="Download"
                    >
                      {u.original_filename}
                    </button>
                  </td>
                  <td>{u.content_type}</td>
                  <td>{formatFileSize(u.file_size_bytes)}</td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="vendor-delete-btn"
                      onClick={() => handleDeleteUpload(u.id)}
                      title="Delete"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {uploadTotal > 20 && (
            <div className="vendor-pagination">
              <button
                className="action-btn"
                disabled={uploadPage <= 1}
                onClick={() => setUploadPage((p) => p - 1)}
              >
                Previous
              </button>
              <span className="vendor-page-info">
                Page {uploadPage} of {Math.ceil(uploadTotal / 20)}
              </span>
              <button
                className="action-btn"
                disabled={uploadPage >= Math.ceil(uploadTotal / 20)}
                onClick={() => setUploadPage((p) => p + 1)}
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
