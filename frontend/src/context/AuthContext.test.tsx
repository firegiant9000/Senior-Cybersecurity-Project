import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { fakeUser, mockFetch } = vi.hoisted(() => {
  const calls: string[] = [];
  const fakeUser = {
    email: "new@example.com",
    emailVerified: false,
    getIdToken: vi.fn(async (force?: boolean) => {
      calls.push(force ? "getIdToken(true)" : "getIdToken()");
      return "token";
    }),
    reload: vi.fn(async () => {
      calls.push("reload");
    }),
    calls,
  };
  return { fakeUser, mockFetch: vi.fn() };
});

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: unknown) => void) => {
    cb(fakeUser);
    return vi.fn();
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendEmailVerification: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("../firebase", () => ({ auth: {} }));

import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { orgLoading, emailUnverified, profileError, confirmVerification } = useAuth();
  return (
    <div>
      <span data-testid="orgLoading">{String(orgLoading)}</span>
      <span data-testid="emailUnverified">{String(emailUnverified)}</span>
      <span data-testid="profileError">{String(profileError)}</span>
      <button onClick={() => confirmVerification()}>confirm</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

const PROFILE = { org_id: 1, org_is_demo: false, role: "viewer", org_role: "member" };

describe("AuthContext profile fetch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fakeUser.calls.length = 0;
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("403 not-verified sets emailUnverified and clears orgLoading", async () => {
    mockFetch.mockResolvedValue(response(403, { detail: "Email address not verified" }));

    renderProvider();

    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("orgLoading")).toHaveTextContent("false");
    expect(screen.getByTestId("profileError")).toHaveTextContent("false");
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("200 clears emailUnverified", async () => {
    mockFetch
      .mockResolvedValueOnce(response(403, { detail: "Email address not verified" }))
      .mockResolvedValueOnce(response(200, PROFILE));

    renderProvider();
    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });

    fireEvent.click(screen.getByText("confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("orgLoading")).toHaveTextContent("false");
  });

  it("other 403 still sets profileError", async () => {
    mockFetch.mockResolvedValue(response(403, { detail: "Account is disabled" }));

    renderProvider();

    await waitFor(
      () => {
        expect(screen.getByTestId("profileError")).toHaveTextContent("true");
      },
      { timeout: 4000 },
    );
    expect(screen.getByTestId("emailUnverified")).toHaveTextContent("false");
  });

  it("confirmVerification reloads and force-refreshes the token", async () => {
    mockFetch
      .mockResolvedValueOnce(response(403, { detail: "Email address not verified" }))
      .mockResolvedValueOnce(response(200, PROFILE));

    renderProvider();
    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });
    fakeUser.calls.length = 0;

    fireEvent.click(screen.getByText("confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("false");
    });
    expect(fakeUser.reload).toHaveBeenCalledTimes(1);
    expect(fakeUser.getIdToken).toHaveBeenCalledWith(true);
    expect(fakeUser.calls.indexOf("reload")).toBeLessThan(fakeUser.calls.indexOf("getIdToken(true)"));
  });
});
