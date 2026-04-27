import { ReactNode } from "react";
import RequiredBadge from "./RequiredBadge";

export interface FormSectionProps {
  title: string;
  description?: string;
  required?: boolean;
  children: ReactNode;
}

export default function FormSection({
  title,
  description,
  required,
  children,
}: FormSectionProps) {
  return (
    <div className="intake-form-section">
      <div className="intake-section-header">
        <h3 className="intake-section-title">{title}</h3>
        <RequiredBadge required={required} optional={required === false} />
      </div>
      {description && <p className="intake-section-description">{description}</p>}
      <div className="intake-section-fields">{children}</div>
    </div>
  );
}
