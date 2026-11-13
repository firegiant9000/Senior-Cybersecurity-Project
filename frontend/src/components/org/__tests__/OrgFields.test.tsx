import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { OrgBasicsFields, type OrgBasicsValue } from "../OrgBasicsFields";
import { RevenueField, toNullable } from "../RevenueField";
import { EMPLOYEE_RANGES, REVENUE_RANGES } from "../../../types/assessmentIntake";

const baseValue: OrgBasicsValue = {
  name: "Acme",
  industry_label: "",
  primary_state: "",
  employee_range: "",
  primary_domain: "",
};

describe("OrgBasicsFields", () => {
  it("selecting a state calls onChange with only that field", () => {
    const onChange = vi.fn();
    render(<OrgBasicsFields value={baseValue} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/Primary State/), {
      target: { value: "TX" },
    });
    expect(onChange).toHaveBeenCalledWith({ primary_state: "TX" });
  });

  it("employee select lists every EMPLOYEE_RANGES entry", () => {
    render(<OrgBasicsFields value={baseValue} onChange={vi.fn()} />);
    const options = within(screen.getByLabelText(/Number of Employees/)).getAllByRole("option");
    const values = options.map((o) => o.getAttribute("value"));
    for (const range of EMPLOYEE_RANGES) {
      expect(values).toContain(range);
    }
  });

  it("disabled disables all five controls", () => {
    render(<OrgBasicsFields value={baseValue} onChange={vi.fn()} disabled />);
    for (const label of [
      /Company Name/,
      /Industry/,
      /Primary State/,
      /Number of Employees/,
      /Primary Domain/,
    ]) {
      expect(screen.getByLabelText(label)).toBeDisabled();
    }
  });
});

describe("RevenueField", () => {
  it("has a blank Prefer not to say option and all revenue ranges", () => {
    render(<RevenueField value="" onChange={vi.fn()} />);
    const options = within(screen.getByLabelText(/Annual Revenue/)).getAllByRole("option");
    expect(options[0].getAttribute("value")).toBe("");
    expect(options[0].textContent).toBe("Prefer not to say");
    expect(options).toHaveLength(REVENUE_RANGES.length + 1);
  });

  it("calls onChange with the selected value and respects disabled", () => {
    const onChange = vi.fn();
    const { rerender } = render(<RevenueField value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/Annual Revenue/), {
      target: { value: REVENUE_RANGES[0] },
    });
    expect(onChange).toHaveBeenCalledWith(REVENUE_RANGES[0]);
    rerender(<RevenueField value="" onChange={onChange} disabled />);
    expect(screen.getByLabelText(/Annual Revenue/)).toBeDisabled();
  });
});

describe("toNullable", () => {
  it("returns null for blank and trims otherwise", () => {
    expect(toNullable("  ")).toBeNull();
    expect(toNullable("")).toBeNull();
    expect(toNullable("  acme.com ")).toBe("acme.com");
  });
});
