import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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

  it("profileError screen unchanged when emailUnverified is false", () => {
    setAuth({ profileError: true });

    renderRoute();

    expect(screen.getByText(/Failed to load your profile/i)).toBeInTheDocument();
    expect(screen.queryByText(/Verify your email address/i)).not.toBeInTheDocument();
  });
});
