import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import SourceBadge from "../SourceBadge";
import { leastConfident } from "../sourceConfidence";

vi.mock("../../../hooks/useDataStatus", () => ({
  useDataStatus: () => ({
    loading: false,
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
  });
});
