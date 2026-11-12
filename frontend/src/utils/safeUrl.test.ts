import { describe, expect, it } from "vitest";
import { httpUrlOrNull, safeNextPath } from "./safeUrl";

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

describe("safeNextPath", () => {
  it.each(['/invites/abc', '/org/findings?x=1#y', '/dashboard?tab=assets'])('accepts %s', (v) => {
    expect(safeNextPath(v)).toBe(v);
  });
  it.each([null, undefined, '', 'dashboard', '//evil.example', '/\\evil.example',
    'https://evil.example', 'javascript:alert(1)', '/a\nb', '/login', '/login?next=/x', '/signup',
    '/\t/evil.example', '/\r/evil.example'])(
    'rejects %j', (v) => { expect(safeNextPath(v)).toBeNull(); });
  it('rejects an encoded double slash once decoded by URLSearchParams', () => {
    expect(safeNextPath(new URLSearchParams('next=%2F%2Fevil.example').get('next'))).toBeNull();
  });
});
