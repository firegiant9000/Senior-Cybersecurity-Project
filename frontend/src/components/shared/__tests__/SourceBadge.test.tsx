import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import SourceBadge from "../SourceBadge";
import { leastConfident } from "../sourceConfidence";

const state = vi.hoisted(() => ({ loading: false }));

vi.mock("../../../hooks/useDataStatus", () => ({
  useDataStatus: () => ({
    loading: state.loading,
    error: null,
    items: [],
    byKey: {
      kev: { key: "kev", status: "real", source: "CISA KEV", notes: null },
      ic3_incidents: { key: "ic3_incidents", status: "static", source: "FBI IC3", notes: null },
    },
  }),
}));

describe("leastConfident", () => {
  it("returns the lowest-confidence status", () => {
    expect(leastConfident(["real", "static"])).toBe("static");
    expect(leastConfident(["real", "pending"])).toBe("pending");
    expect(leastConfident(["real", "mocked", "static"])).toBe("mocked");
    expect(leastConfident(["real"])).toBe("real");
  });

  it("returns null when any status is unknown", () => {
    expect(leastConfident(["real", null])).toBeNull();
  });
});

describe("SourceBadge", () => {
  afterEach(() => {
    state.loading = false;
  });

  it("while loading, an absent entry ignores the fallback status but keeps the fallback source", () => {
    state.loading = true;
    render(
      <SourceBadge datasetKey="not_registered" fallbackStatus="real" fallbackSource="Inline src" />,
    );
    const el = screen.getByText("…").closest("span");
    expect(el?.className).toContain("source-badge--unknown");
    expect(el?.getAttribute("aria-label")).toContain("Inline src");
    expect(el?.getAttribute("aria-label")).not.toContain("Source not registered");
    expect(screen.queryByText("Live")).toBeNull();
  });

  it("while loading, an absent entry without a fallback says loading, not unregistered", () => {
    state.loading = true;
    render(
      <>
        <SourceBadge datasetKey="not_registered" />
        <SourceBadge datasetKeys={["not_registered", "also_missing"]} />
      </>,
    );
    for (const el of screen.getAllByText("…")) {
      const label = el.closest("span")?.getAttribute("aria-label") ?? "";
      expect(label).toContain("Loading source");
      expect(label).not.toMatch(/not registered|unregistered/);
    }
  });

  it("after loading, an absent entry uses the fallback label", () => {
    state.loading = false;
    render(<SourceBadge datasetKey="not_registered" fallbackStatus="real" />);
    expect(screen.getByText("Live")).toBeTruthy();
  });

  it("single datasetKey behaves as before", () => {
    render(<SourceBadge datasetKey="kev" />);
    const el = screen.getByText("Live").closest("span");
    expect(el?.getAttribute("data-dataset-key")).toBe("kev");
    expect(el?.getAttribute("aria-label")).toContain("CISA KEV");
  });

  it("datasetKeys resolves to the least confident status", () => {
    render(<SourceBadge datasetKeys={["kev", "ic3_incidents"]} />);
    const el = screen.getByText("Static").closest("span");
    expect(el?.getAttribute("data-dataset-key")).toBe("kev,ic3_incidents");
    expect(el?.getAttribute("aria-label")).toContain("CISA KEV + FBI IC3");
  });

  it("an unregistered key reads ? and never Live", () => {
    render(<SourceBadge datasetKeys={["kev", "not_registered"]} />);
    expect(screen.getByText("?")).toBeTruthy();
    expect(screen.queryByText("Live")).toBeNull();
    const el = screen.getByText("?").closest("span");
    expect(el?.getAttribute("aria-label")).toContain("CISA KEV + unregistered (not_registered)");
  });

  it("empty datasetKeys reads ?", () => {
    render(<SourceBadge datasetKeys={[]} />);
    expect(screen.getByText("?")).toBeTruthy();
  });

  it("single unregistered key uses fallbackStatus and fallbackSource", () => {
    render(
      <SourceBadge datasetKey="not_registered" fallbackStatus="static" fallbackSource="Inline src" />,
    );
    const el = screen.getByText("Static").closest("span");
    expect(el?.getAttribute("aria-label")).toContain("Inline src");
  });
});
