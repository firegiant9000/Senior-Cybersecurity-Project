import RequiredBadge from "../shared/RequiredBadge";
import {
  INDUSTRY_OPTIONS,
  EMPLOYEE_RANGES,
  US_STATES,
} from "../../types/assessmentIntake";

export interface OrgBasicsValue {
  name: string;
  industry_label: string;
  primary_state: string;
  employee_range: string;
  primary_domain: string;
}

interface OrgBasicsFieldsProps {
  value: OrgBasicsValue;
  onChange: (patch: Partial<OrgBasicsValue>) => void;
  disabled?: boolean;
  /** Focus the name input on mount (wizard only). */
  autoFocusName?: boolean;
  /** Caller-owned validation message shown under the domain input. */
  domainError?: string;
}

export function OrgBasicsFields({
  value,
  onChange,
  disabled,
  autoFocusName,
  domainError,
}: OrgBasicsFieldsProps) {
  return (
    <>
      <div className="intake-form-group">
        <label htmlFor="name">
          Company Name
          <RequiredBadge required />
        </label>
        <input
          id="name"
          type="text"
          value={value.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Acme Corporation"
          maxLength={255}
          disabled={disabled}
          autoFocus={autoFocusName}
        />
      </div>

      <div className="intake-form-group">
        <label htmlFor="industry">
          Industry
          <RequiredBadge required />
        </label>
        <select
          id="industry"
          value={value.industry_label}
          onChange={(e) => onChange({ industry_label: e.target.value })}
          disabled={disabled}
        >
          <option value="">Select your industry</option>
          {INDUSTRY_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>

      <div className="intake-form-group">
        <label htmlFor="state">
          Primary State
          <RequiredBadge required />
        </label>
        <select
          id="state"
          value={value.primary_state}
          onChange={(e) => onChange({ primary_state: e.target.value })}
          disabled={disabled}
        >
          <option value="">Select your state</option>
          {US_STATES.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div className="intake-form-group">
        <label htmlFor="employees">
          Number of Employees
          <RequiredBadge required />
        </label>
        <select
          id="employees"
          value={value.employee_range}
          onChange={(e) => onChange({ employee_range: e.target.value })}
          disabled={disabled}
        >
          <option value="">Select company size</option>
          {EMPLOYEE_RANGES.map((opt) => (
            <option key={opt} value={opt}>
              {opt} employees
            </option>
          ))}
        </select>
      </div>

      <div className="intake-form-group">
        <label htmlFor="primary_domain">
          Primary Domain
          <RequiredBadge optional />
        </label>
        <p className="intake-field-hint">
          Used for domain-based threat exposure checks (DNS, SSL, breach data).
        </p>
        <input
          id="primary_domain"
          type="text"
          value={value.primary_domain}
          onChange={(e) => onChange({ primary_domain: e.target.value })}
          placeholder="acme.com"
          maxLength={255}
          autoComplete="off"
          disabled={disabled}
        />
        {domainError && <p className="intake-field-error">{domainError}</p>}
      </div>
    </>
  );
}
