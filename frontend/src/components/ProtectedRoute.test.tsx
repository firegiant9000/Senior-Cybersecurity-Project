import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";

const { authState } = vi.hoisted(() => ({
  authState: {
    value: {} as Record<string, unknown>,
  },
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => authState.value,
}));

import ProtectedRoute from "./ProtectedRoute";

function setAuth(overrides: Record<string, unknown>) {
  authState.value = {
    user: { email: "new@example.com", emailVerified: false },
    loading: false,
    orgId: 1,
    orgLoading: false,
    profileError: false,
    emailUnverified: false,
    signedOutDeliberately: false,
    refreshProfile: vi.fn(),
    resendVerification: vi.fn(),
    confirmVerification: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  };
}

function renderRoute() {
  return render(
    <MemoryRouter>
      <ProtectedRoute>
        <p>protected content</p>
      </ProtectedRoute>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("shows verify panel when emailUnverified", () => {
    setAuth({ emailUnverified: true });

    renderRoute();

    expect(screen.getByText(/Verify your email address to continue/i)).toBeInTheDocument();
    expect(screen.getByText(/new@example\.com/)).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("verified in Firebase but server still refuses shows the message", async () => {
    const confirmVerification = vi.fn().mockResolvedValue(false);
    setAuth({
      emailUnverified: true,
      user: { email: "new@example.com", emailVerified: true },
      confirmVerification,
    });

    renderRoute();
    fireEvent.click(screen.getByRole("button", { name: /I've verified my email/i }));

    expect(await screen.findByText(/We couldn't confirm your address yet/i)).toBeInTheDocument();
    expect(confirmVerification).toHaveBeenCalledTimes(1);
  });

  it("signed out: redirects to /login with the requested URL in ?next=", () => {
    setAuth({ user: null });

    function LoginSearch() {
      return <p data-testid="login-search">{useLocation().search}</p>;
    }

    render(
      <MemoryRouter initialEntries={["/invites/tok123?x=1#h"]}>
        <Routes>
          <Route path="/login" element={<LoginSearch />} />
          <Route
            path="/invites/:token"
            element={
              <ProtectedRoute>
                <p>protected content</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("login-search")).toHaveTextContent("?next=%2Finvites%2Ftok123%3Fx%3D1%23h");
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("deliberate sign-out: goes to / and never to /login", () => {
    setAuth({ user: null, signedOutDeliberately: true });

    function Where({ label }: { label: string }) {
      const l = useLocation();
      return <p data-testid={label}>{l.pathname + l.search}</p>;
    }

    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/" element={<Where label="home" />} />
          <Route path="/login" element={<Where label="login" />} />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <p>protected content</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("home")).toHaveTextContent("/");
    expect(screen.queryByTestId("login")).not.toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("profileError screen unchanged when emailUnverified is false", () => {
    setAuth({ profileError: true });

    renderRoute();

    expect(screen.getByText(/Failed to load your profile/i)).toBeInTheDocument();
    expect(screen.queryByText(/Verify your email address/i)).not.toBeInTheDocument();
  });
});
