import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../fetchWithAuth", () => ({
  API_BASE_URL: "http://api.test",
  fetchWithAuth: vi.fn(),
}));

import { fetchWithAuth } from "../fetchWithAuth";
import { LONG_TIMEOUT_MS } from "../timeouts";
import { uploadFile } from "../uploads";
import { previewInventoryCsv, importInventoryCsv } from "../inventory";
import { importVendorsCsv, previewVendorsCsv } from "../vendors";

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
    } as unknown as Response);
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
});
