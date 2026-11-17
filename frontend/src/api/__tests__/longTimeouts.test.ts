import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../fetchWithAuth", () => ({
  API_BASE_URL: "http://api.test",
  fetchWithAuth: vi.fn(),
  getJsonAuth: vi.fn(),
}));

import { fetchWithAuth } from "../fetchWithAuth";
import { LONG_TIMEOUT_MS, RequestTimeoutError } from "../timeouts";
import { uploadFile, downloadUpload } from "../uploads";
import { previewInventoryCsv, importInventoryCsv } from "../inventory";
import { importVendorsCsv, previewVendorsCsv } from "../vendors";
import { syncM365 } from "../integrations";

const mockFetch = vi.mocked(fetchWithAuth);
const file = new File(["a"], "a.csv");

function expectLongTimeout() {
  expect(mockFetch).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({ timeoutMs: LONG_TIMEOUT_MS }),
  );
}

describe("slow calls use LONG_TIMEOUT_MS", () => {
  beforeEach(() => {
    mockFetch.mockReset().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
      blob: async () => new Blob(["x"]),
    } as unknown as Response);
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(window.HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("uploadFile", async () => {
    await uploadFile(1, file);
    expectLongTimeout();
  });

  it("previewInventoryCsv", async () => {
    await previewInventoryCsv(1, file);
    expectLongTimeout();
  });

  it("importInventoryCsv", async () => {
    await importInventoryCsv(1, file);
    expectLongTimeout();
  });

  it("importVendorsCsv", async () => {
    await importVendorsCsv(1, file);
    expectLongTimeout();
  });

  it("previewVendorsCsv", async () => {
    await previewVendorsCsv(1, file);
    expectLongTimeout();
  });

  it("syncM365", async () => {
    await syncM365(1);
    expectLongTimeout();
  });

  it("downloadUpload", async () => {
    await downloadUpload(1, 2, "a.csv");
    expectLongTimeout();
  });

  it("downloadUpload converts a body-read timeout into RequestTimeoutError", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      blob: () =>
        Promise.reject(new DOMException("signal timed out", "TimeoutError")),
    } as unknown as Response);

    await expect(downloadUpload(1, 2, "a.csv")).rejects.toBeInstanceOf(
      RequestTimeoutError,
    );
  });
});
