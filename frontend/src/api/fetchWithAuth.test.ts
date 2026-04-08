import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Mock firebase/app & firebase/auth before any imports ─────────────────
// vi.mock factories are hoisted — cannot reference outer variables.
// Use vi.hoisted to declare shared mocks that both the factory and tests can access.
const { mockSignOut, mockGetIdToken } = vi.hoisted(() => ({
  mockSignOut: vi.fn().mockResolvedValue(undefined),
  mockGetIdToken: vi.fn().mockResolvedValue("fake-token"),
}));

vi.mock("firebase/app", () => ({
  initializeApp: vi.fn(() => ({})),
}));

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({
    currentUser: { getIdToken: mockGetIdToken },
  })),
  signOut: mockSignOut,
}));

import {
  fetchWithAuth,
  getJsonAuth,
  ForbiddenError,
  _resetForTest,
} from "./fetchWithAuth";
import { auth } from "../firebase";

// ── Helpers ──────────────────────────────────────────────────────────────
function mockFetchResponse(status: number, body: unknown = {}) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    statusText: status === 200 ? "OK" : "Error",
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response);
}

// ── Tests ────────────────────────────────────────────────────────────────
describe("fetchWithAuth", () => {
  const originalLocation = window.location.href;

  beforeEach(() => {
    _resetForTest();
    vi.restoreAllMocks();
    mockSignOut.mockReset().mockResolvedValue(undefined);
    mockGetIdToken.mockReset().mockResolvedValue("fake-token");
    // auth mock always has a current user with a token
    (auth as unknown as { currentUser: { getIdToken: typeof mockGetIdToken } }).currentUser = {
      getIdToken: mockGetIdToken,
    };
    // Reset location
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: originalLocation },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: originalLocation },
    });
  });

  it("attaches Bearer token to requests", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 200,
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    } as unknown as Response);

    await fetchWithAuth("https://api.test/endpoint");

    expect(spy).toHaveBeenCalledWith(
      "https://api.test/endpoint",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer fake-token",
        }),
      }),
    );
  });

  it("does not attach Authorization header when no user is logged in", async () => {
    (auth as unknown as { currentUser: null }).currentUser = null;

    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 200,
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    } as unknown as Response);

    await fetchWithAuth("https://api.test/endpoint");

    const headers = spy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  // ── 401 handling ────────────────────────────────────────────────────────
  describe("401 responses", () => {
    it("signs out and redirects to /login", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(401, {}),
      );

      await fetchWithAuth("https://api.test/endpoint");

      expect(mockSignOut).toHaveBeenCalledWith(auth);
      expect(window.location.href).toBe("/login");
    });

    it("resets isLoggingOut flag after signOut completes so future 401s still work", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(401, {}),
      );

      // First 401
      await fetchWithAuth("https://api.test/first");
      expect(mockSignOut).toHaveBeenCalledTimes(1);

      // Reset location to simulate user navigating back
      window.location.href = "/";

      // Second 401 should still trigger sign-out
      await fetchWithAuth("https://api.test/second");
      expect(mockSignOut).toHaveBeenCalledTimes(2);
    });

    it("resets isLoggingOut flag even if signOut throws", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(401, {}),
      );
      mockSignOut.mockRejectedValueOnce(new Error("network error"));

      // Should not throw
      await fetchWithAuth("https://api.test/endpoint");
      expect(window.location.href).toBe("/login");

      // Should still work on next 401
      window.location.href = "/";
      await fetchWithAuth("https://api.test/endpoint2");
      expect(mockSignOut).toHaveBeenCalledTimes(2);
    });

    it("still redirects to /login even during concurrent logout", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(401, {}),
      );

      // First call signs out + redirects
      await fetchWithAuth("https://api.test/first");
      expect(mockSignOut).toHaveBeenCalledTimes(1);
      expect(window.location.href).toBe("/login");

      // Simulate user somehow still on a page — second 401 should still redirect
      window.location.href = "/dashboard";
      await fetchWithAuth("https://api.test/second");

      // Both calls redirect (signOut called twice since flag resets)
      expect(window.location.href).toBe("/login");
    });
  });

  // ── 403 handling ────────────────────────────────────────────────────────
  describe("403 responses", () => {
    it("throws ForbiddenError with backend detail message", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(403, { detail: "Admin role required" }),
      );

      await expect(
        fetchWithAuth("https://api.test/endpoint"),
      ).rejects.toThrow(ForbiddenError);

      await expect(
        fetchWithAuth("https://api.test/endpoint"),
      ).rejects.toThrow("Admin role required");
    });

    it("throws ForbiddenError with default message when body has no detail", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        mockFetchResponse(403, {}),
      );

      await expect(
        fetchWithAuth("https://api.test/endpoint"),
      ).rejects.toThrow("You do not have permission to perform this action");
    });

    it("throws ForbiddenError even when response body is unparseable", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        status: 403,
        ok: false,
        json: vi.fn().mockRejectedValue(new Error("invalid json")),
      } as unknown as Response);

      await expect(
        fetchWithAuth("https://api.test/endpoint"),
      ).rejects.toThrow(ForbiddenError);
    });
  });

  // ── Normal responses pass through ──────────────────────────────────────
  it("returns response as-is for non-401/403 status codes", async () => {
    const mockResponse = {
      status: 200,
      ok: true,
      json: vi.fn().mockResolvedValue({ data: "test" }),
    } as unknown as Response;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse);

    const result = await fetchWithAuth("https://api.test/endpoint");
    expect(result).toBe(mockResponse);
  });

  it("returns response as-is for 500 errors (no special handling)", async () => {
    const mockResponse = {
      status: 500,
      ok: false,
      json: vi.fn().mockResolvedValue({ detail: "server error" }),
    } as unknown as Response;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse);

    const result = await fetchWithAuth("https://api.test/endpoint");
    expect(result).toBe(mockResponse);
  });
});

describe("getJsonAuth", () => {
  beforeEach(() => {
    _resetForTest();
    vi.restoreAllMocks();
    mockSignOut.mockReset().mockResolvedValue(undefined);
    mockGetIdToken.mockReset().mockResolvedValue("fake-token");
    (auth as unknown as { currentUser: { getIdToken: typeof mockGetIdToken } }).currentUser = {
      getIdToken: mockGetIdToken,
    };
  });

  it("returns parsed JSON on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 200,
      ok: true,
      json: vi.fn().mockResolvedValue({ result: 42 }),
    } as unknown as Response);

    const controller = new AbortController();
    const data = await getJsonAuth<{ result: number }>(
      "https://api.test/data",
      controller.signal,
    );
    expect(data).toEqual({ result: 42 });
  });

  it("throws on non-ok responses that are not 401/403", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 500,
      ok: false,
      statusText: "Internal Server Error",
      json: vi.fn().mockResolvedValue({ detail: "db connection failed" }),
    } as unknown as Response);

    const controller = new AbortController();
    await expect(
      getJsonAuth("https://api.test/data", controller.signal),
    ).rejects.toThrow("db connection failed");
  });
});
