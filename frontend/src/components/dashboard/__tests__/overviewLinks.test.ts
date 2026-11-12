import { describe, expect, it, vi } from "vitest";

// Importing InventoryHealthCard pulls in AuthContext, which initialises Firebase.
// Mock it as the neighbouring tests do.
vi.mock("firebase/app", () => ({
  initializeApp: vi.fn(() => ({})),
}));

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn(),
  signOut: vi.fn(),
}));

import { NEXT_STEPS } from "../NextStepsCard";
import { assetsLinkTarget } from "../InventoryHealthCard";

describe("Overview links", () => {
  it("next steps point at real routes", () => {
    const to = Object.fromEntries(NEXT_STEPS.map((s) => [s.title, s.to]));
    expect(to["Upload CSV inventory"]).toBe("/inventory/upload");
    expect(to["Connect Microsoft 365"]).toBe("/integrations");
  });

  it("assets link keeps the tab", () => {
    expect(assetsLinkTarget(3)).toBe("/dashboard?tab=assets");
    expect(assetsLinkTarget(0)).toBe("/inventory/upload");
  });
});
