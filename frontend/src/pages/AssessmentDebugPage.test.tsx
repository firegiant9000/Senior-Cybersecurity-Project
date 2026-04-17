import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_a: unknown, cb: (u: null) => void) => { cb(null); return vi.fn(); }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}));
vi.mock("firebase/app", () => ({ initializeApp: vi.fn(() => ({})) }));

const mockAuthValues = {
  user: { uid: "u1", email: "admin@example.com" } as unknown,
  loading: false,
  orgId: 1 as number | null,
  orgLoading: false,
  profileError: false,
  role: null as string | null,
  orgRole: "admin" as string | null,
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

vi.mock("../api/fetchWithAuth", () => ({
  API_BASE_URL: "",
  fetchWithAuth: vi.fn(),
  getJsonAuth: vi.fn(),
}));

const mockDebugResponse = {
  generated_at: "2024-01-01T00:00:00Z",
  org_id: 1,
  raw_profile: { name: "Acme", industry_label: "Technology" },
  intake: {
    current_tier: "enhanced",
    tiers: [],
    next_tier: "comprehensive",
    next_tier_progress: 50,
    fields_to_advance: ["revenue_range"],
  },
  validation: {
    issues: [],
    score: 95,
    passed: true,
    issue_counts: { error: 0, warning: 0, info: 1 },
  },
  findings_readiness: {
    ready: true,
    current_tier: "enhanced",
    blocking_reason: null,
    report: {
      org_id: 1,
      findings: [],
      summary: { total: 0, by_type: {}, by_severity: {} },
      generated_at: "2024-01-01T00:00:00Z",
      data_sources_used: [],
      assessment_tier: "enhanced",
    },
  },
};

vi.mock("../api/assessmentDebug", () => ({
  fetchAssessmentDebug: vi.fn(() => Promise.resolve(mockDebugResponse)),
}));

import AssessmentDebugPage from "./AssessmentDebugPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <AssessmentDebugPage />
    </MemoryRouter>,
  );
}

describe("AssessmentDebugPage", () => {
  beforeEach(() => {
    mockAuthValues.role = null;
    mockAuthValues.orgRole = "admin";
  });

  it("renders all four section headings after load", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Raw Inputs")).toBeTruthy();
      expect(screen.getByText(/Normalized/)).toBeTruthy();
      expect(screen.getByText("Validation")).toBeTruthy();
      expect(screen.getByText(/Exposure/)).toBeTruthy();
    });
  });

  it("shows loading state initially", () => {
    const { getByText } = renderPage();
    expect(getByText(/Loading debug snapshot/i)).toBeTruthy();
  });

  it("shows not-ready message when findings readiness is false", async () => {
    const { fetchAssessmentDebug } = await import("../api/assessmentDebug");
    (fetchAssessmentDebug as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...mockDebugResponse,
      findings_readiness: {
        ready: false,
        current_tier: "basic",
        blocking_reason: "Needs Enhanced tier",
        report: null,
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Needs Enhanced tier/i)).toBeTruthy();
    });
  });

  it("shows error state when fetch fails", async () => {
    const { fetchAssessmentDebug } = await import("../api/assessmentDebug");
    (fetchAssessmentDebug as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Network error"),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeTruthy();
    });
  });
});
