import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockFetchWithAuth } = vi.hoisted(() => ({
  mockFetchWithAuth: vi.fn(),
}));

vi.mock("../fetchWithAuth", () => ({
  API_BASE_URL: "http://api",
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
}));

import { fetchMe } from "../account";

describe("fetchMe", () => {
  beforeEach(() => {
    mockFetchWithAuth.mockReset();
  });

  it("returns the profile from GET /api/v1/auth/me", async () => {
    const profile = {
      id: 1,
      email: "user@example.com",
      is_active: true,
      role: "user",
      auth_provider: "firebase",
      created_at: "2024-01-01T00:00:00Z",
      org_id: null,
      org_role: null,
    };
    mockFetchWithAuth.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(profile),
    });

    await expect(fetchMe()).resolves.toEqual(profile);
    expect(mockFetchWithAuth).toHaveBeenCalledWith(
      "http://api/api/v1/auth/me",
    );
  });

  it("throws 'Failed to load profile' on a non-ok response", async () => {
    mockFetchWithAuth.mockResolvedValue({ ok: false });

    await expect(fetchMe()).rejects.toThrow("Failed to load profile");
  });
});
