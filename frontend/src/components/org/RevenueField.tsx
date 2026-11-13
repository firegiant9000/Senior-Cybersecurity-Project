import RequiredBadge from "../shared/RequiredBadge";
import { REVENUE_RANGES } from "../../types/assessmentIntake";

interface RevenueFieldProps {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}

/** Trims; an empty value becomes null (organisation PUT bodies never send ""). */
export function toNullable(v: string): string | null {
  const trimmed = v.trim();
  return trimmed === "" ? null : trimmed;
}

export function RevenueField({ value, onChange, disabled }: RevenueFieldProps) {
  return (
    <div className="intake-form-group">
      <label htmlFor="revenue">
        Annual Revenue
        <RequiredBadge optional />
      </label>
      <p className="intake-field-hint intake-field-hint--optional">
        Optional — affects loss-projection accuracy.
      </p>
      <select
        id="revenue"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        <option value="">Prefer not to say</option>
        {REVENUE_RANGES.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
