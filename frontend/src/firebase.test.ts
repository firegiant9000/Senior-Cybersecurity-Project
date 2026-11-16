import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const connectAuthEmulator = vi.fn();

vi.mock("firebase/app", () => ({ initializeApp: vi.fn(() => ({})) }));
vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({})),
  connectAuthEmulator: (...args: unknown[]) => connectAuthEmulator(...args),
}));

describe("firebase auth emulator wiring", () => {
  beforeEach(() => {
    vi.resetModules();
    connectAuthEmulator.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("connects to the emulator in dev when the URL is set", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_FIREBASE_AUTH_EMULATOR_URL", "http://localhost:9099");
    await import("./firebase");
    expect(connectAuthEmulator).toHaveBeenCalledWith(expect.anything(), "http://localhost:9099", {
      disableWarnings: true,
    });
  });

  it("does not connect outside dev even when the URL is set", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_FIREBASE_AUTH_EMULATOR_URL", "http://localhost:9099");
    await import("./firebase");
    expect(connectAuthEmulator).not.toHaveBeenCalled();
  });

  it("does not connect when the URL is unset", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_FIREBASE_AUTH_EMULATOR_URL", "");
    await import("./firebase");
    expect(connectAuthEmulator).not.toHaveBeenCalled();
  });

  it("refuses a non-localhost emulator URL", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_FIREBASE_AUTH_EMULATOR_URL", "http://emulator.example.com:9099");
    await expect(import("./firebase")).rejects.toThrow("Auth emulator URL must be localhost");
    expect(connectAuthEmulator).not.toHaveBeenCalled();
  });
});
