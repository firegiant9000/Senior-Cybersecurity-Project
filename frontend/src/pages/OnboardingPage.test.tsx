import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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

const mockAuthValues = {
  user: { uid: "u1", email: "user@example.com" } as unknown,
  loading: false,
  orgId: null as number | null,
  orgLoading: false,
  profileError: false,
  role: null as string | null,
  orgRole: null as string | null,
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  getIdToken: vi.fn(),
  refreshProfile: vi.fn(),
};

vi.mock("../context/AuthContext", () => ({
  useAuth: () => mockAuthValues,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockFetchWithAuth = vi.fn();
vi.mock("../api/fetchWithAuth", () => ({
  API_BASE_URL: "",
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
  getJsonAuth: vi.fn(),
}));

import OnboardingPage from "./OnboardingPage";

const mockOnComplete = vi.fn();

function renderPage() {
  return render(
    <MemoryRouter>
      <OnboardingPage onComplete={mockOnComplete} />
    </MemoryRouter>,
  );
}

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthValues.orgId = null;
  });

  it("renders step 1 without crashing", () => {
    renderPage();
    expect(screen.getByText("Set Up Your Organization")).toBeTruthy();
    expect(screen.getByText("Step 1 of 9")).toBeTruthy();
    expect(screen.getByLabelText("Company Name")).toBeTruthy();
  });

  it("Continue button is disabled until company name is entered", () => {
    renderPage();
    const continueBtn = screen.getByRole("button", { name: "Continue" });
    expect(continueBtn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Company Name"), {
      target: { value: "Acme Corp" },
    });
    expect(continueBtn).not.toBeDisabled();
  });

  it("submits successfully after filling required fields", async () => {
    mockFetchWithAuth.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    renderPage();

    // Step 1: company name
    fireEvent.change(screen.getByLabelText("Company Name"), { target: { value: "Acme Corp" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 2: industry
    fireEvent.change(screen.getByLabelText("Industry"), {
      target: { value: "Finance & Insurance" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 3: state
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "CA" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 4: employee range
    fireEvent.change(screen.getByLabelText("Number of Employees"), { target: { value: "1-10" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 5: skip remaining optional steps and submit
    fireEvent.click(screen.getByRole("button", { name: "Skip remaining and finish" }));

    await waitFor(() => {
      expect(mockFetchWithAuth).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/onboarding/complete"),
        expect.objectContaining({ method: "POST" }),
      );
      expect(mockOnComplete).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error when API returns failure", async () => {
    mockFetchWithAuth.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Organization name already taken" }),
    });
    renderPage();

    fireEvent.change(screen.getByLabelText("Company Name"), { target: { value: "Acme Corp" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(screen.getByLabelText("Industry"), {
      target: { value: "Finance & Insurance" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "CA" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(screen.getByLabelText("Number of Employees"), { target: { value: "1-10" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip remaining and finish" }));

    await waitFor(() => {
      expect(screen.getByText("Organization name already taken")).toBeTruthy();
    });
  });

  it("redirects to dashboard when org already exists", () => {
    mockAuthValues.orgId = 1;
    renderPage();
    expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
  });
});
