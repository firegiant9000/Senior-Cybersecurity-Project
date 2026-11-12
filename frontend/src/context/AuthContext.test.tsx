import { act, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { fakeUser, mockFetch, authListener } = vi.hoisted(() => {
  const authListener: { current: ((u: unknown) => void) | null } = { current: null };
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
  return { fakeUser, mockFetch: vi.fn(), authListener };
});

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: unknown) => void) => {
    authListener.current = cb;
    cb(fakeUser);
    return vi.fn();
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendEmailVerification: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("../firebase", () => ({ auth: {} }));

import { signOut } from "firebase/auth";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { orgLoading, emailUnverified, profileError, confirmVerification } = useAuth();
  const [result, setResult] = useState("");
  return (
    <div>
      <span data-testid="orgLoading">{String(orgLoading)}</span>
      <span data-testid="emailUnverified">{String(emailUnverified)}</span>
      <span data-testid="profileError">{String(profileError)}</span>
      <span data-testid="confirmResult">{result}</span>
      <button onClick={async () => setResult(String(await confirmVerification()))}>confirm</button>
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

  it("a different user whose profile fetch fails does not inherit the verify screen", async () => {
    mockFetch.mockResolvedValueOnce(response(403, { detail: "Email address not verified" }));

    renderProvider();
    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });

    mockFetch.mockResolvedValue(response(500, {}));
    const otherUser = { ...fakeUser, email: "other@example.com", emailVerified: true };
    act(() => {
      authListener.current?.(otherUser);
    });

    await waitFor(
      () => {
        expect(screen.getByTestId("profileError")).toHaveTextContent("true");
      },
      { timeout: 4000 },
    );
    expect(screen.getByTestId("emailUnverified")).toHaveTextContent("false");
  });

  it("confirmVerification on a still-unverified user keeps the verify screen while in flight", async () => {
    mockFetch.mockResolvedValueOnce(response(403, { detail: "Email address not verified" }));

    renderProvider();
    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });

    let release: (r: unknown) => void = () => {};
    mockFetch.mockReturnValueOnce(new Promise((resolve) => (release = resolve)));
    fireEvent.click(screen.getByText("confirm"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");

    release(response(403, { detail: "Email address not verified" }));
    await waitFor(() => {
      expect(screen.getByTestId("confirmResult")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
  });

  it("confirmVerification resolves false while the server still refuses, true once it accepts", async () => {
    mockFetch
      .mockResolvedValueOnce(response(403, { detail: "Email address not verified" }))
      .mockResolvedValueOnce(response(403, { detail: "Email address not verified" }))
      .mockResolvedValueOnce(response(200, PROFILE));

    renderProvider();
    await waitFor(() => {
      expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");
    });

    fireEvent.click(screen.getByText("confirm"));
    await waitFor(() => {
      expect(screen.getByTestId("confirmResult")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("emailUnverified")).toHaveTextContent("true");

    fireEvent.click(screen.getByText("confirm"));
    await waitFor(() => {
      expect(screen.getByTestId("confirmResult")).toHaveTextContent("true");
    });
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

describe("AuthContext signedOutDeliberately", () => {
  const renders: Array<{ signedOut: boolean; flag: boolean }> = [];

  function FlagProbe() {
    const { user, signedOutDeliberately, logout } = useAuth();
    renders.push({ signedOut: user === null, flag: signedOutDeliberately });
    return (
      <div>
        <span data-testid="flag">{String(signedOutDeliberately)}</span>
        <span data-testid="user">{user ? "in" : "out"}</span>
        <button onClick={() => logout().catch(() => {})}>logout</button>
      </div>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    renders.length = 0;
    vi.stubGlobal("fetch", mockFetch);
    mockFetch.mockResolvedValue(response(200, PROFILE));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is set before the listener nulls the user, and cleared when a user signs in again", async () => {
    vi.mocked(signOut).mockImplementation(async () => {
      authListener.current!(null);
    });
    render(
      <AuthProvider>
        <FlagProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("in"));
    expect(screen.getByTestId("flag")).toHaveTextContent("false");

    fireEvent.click(screen.getByText("logout"));

    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("out"));
    expect(screen.getByTestId("flag")).toHaveTextContent("true");
    // After the first signed-in render (the provider starts with user null before its listener
    // runs), no render shows a signed-out user without the flag.
    const afterSignIn = renders.slice(renders.findIndex((r) => !r.signedOut));
    expect(afterSignIn.some((r) => r.signedOut)).toBe(true);
    expect(afterSignIn.filter((r) => r.signedOut && !r.flag)).toEqual([]);

    act(() => {
      authListener.current!(fakeUser);
    });
    await waitFor(() => expect(screen.getByTestId("flag")).toHaveTextContent("false"));
  });

  it("does not stay set when signOut fails", async () => {
    vi.mocked(signOut).mockRejectedValue(new Error("network"));
    render(
      <AuthProvider>
        <FlagProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("in"));

    fireEvent.click(screen.getByText("logout"));

    await waitFor(() => expect(signOut).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("flag")).toHaveTextContent("false"));
    expect(screen.getByTestId("user")).toHaveTextContent("in");
  });
});
