import { describe, expect, it } from "vitest";
import { httpUrlOrNull } from "./safeUrl";

describe("httpUrlOrNull", () => {
  it("accepts http and https, trimmed", () => {
    expect(httpUrlOrNull("  https://example.com/logo.png ")).toBe("https://example.com/logo.png");
    expect(httpUrlOrNull("HTTPS://Example.com/a.png")).toBe("https://example.com/a.png");
    expect(httpUrlOrNull("http://example.com/a.png")).toBe("http://example.com/a.png");
  });
  it("rejects everything else", () => {
    for (const v of ["", "   ", "javascript:alert(1)", "data:image/png;base64,AAAA", "//example.com/a.png", "not a url"]) {
      expect(httpUrlOrNull(v)).toBeNull();
    }
  });
});
