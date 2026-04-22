import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_a: unknown, cb: (u: null) => void) => {
    cb(null);
    return vi.fn();
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}));
vi.mock("firebase/app", () => ({ initializeApp: vi.fn(() => ({})) }));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockRefreshProfile = vi.fn();
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ refreshProfile: mockRefreshProfile }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockGetInviteByToken = vi.fn();
const mockAcceptInvite = vi.fn();
vi.mock("../api/members", () => ({
  getInviteByToken: (...args: unknown[]) => mockGetInviteByToken(...args),
  acceptInvite: (...args: unknown[]) => mockAcceptInvite(...args),
}));

import AcceptInvitePage from "./AcceptInvitePage";

const mockInvite = {
  invite_token: "test-token-123",
  org_name: "Acme Corp",
  org_role: "member",
  invited_email: "user@example.com",
  expires_at: "2026-12-31T00:00:00Z",
};

function renderPage(token = "test-token-123") {
  return render(
    <MemoryRouter initialEntries={[`/invite/${token}`]}>
      <Routes>
        <Route path="/invite/:token" element={<AcceptInvitePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AcceptInvitePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders invite details after loading", async () => {
    mockGetInviteByToken.mockResolvedValueOnce(mockInvite);
    renderPage();
    expect(screen.getByText("Loading invite...")).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeTruthy();
      expect(screen.getByText("member")).toBeTruthy();
      expect(screen.getByText("user@example.com")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Accept & Join" })).toBeTruthy();
    });
  });

  it("calls acceptInvite with token and shows success message", async () => {
    mockGetInviteByToken.mockResolvedValueOnce(mockInvite);
    mockAcceptInvite.mockResolvedValueOnce(undefined);
    mockRefreshProfile.mockResolvedValueOnce(undefined);
    renderPage();

    await waitFor(() => screen.getByRole("button", { name: "Accept & Join" }));
    fireEvent.click(screen.getByRole("button", { name: "Accept & Join" }));

    await waitFor(() => {
      expect(mockAcceptInvite).toHaveBeenCalledWith("test-token-123");
      expect(screen.getByText(/You have joined the organization/)).toBeTruthy();
    });
  });

  it("shows error on rejection", async () => {
    mockGetInviteByToken.mockResolvedValueOnce(mockInvite);
    mockAcceptInvite.mockRejectedValueOnce(new Error("Invite already used"));
    renderPage();

    await waitFor(() => screen.getByRole("button", { name: "Accept & Join" }));
    fireEvent.click(screen.getByRole("button", { name: "Accept & Join" }));

    await waitFor(() => {
      expect(screen.getByText("Invite already used")).toBeTruthy();
    });
  });

  it("shows error when invite token is invalid", async () => {
    mockGetInviteByToken.mockRejectedValueOnce(new Error("Invite not found"));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Invite not found")).toBeTruthy();
    });
  });
});
