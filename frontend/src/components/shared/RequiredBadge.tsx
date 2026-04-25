export interface RequiredBadgeProps {
  required?: boolean;
  optional?: boolean;
}

export default function RequiredBadge({ required, optional }: RequiredBadgeProps) {
  if (!required && !optional) return null;

  return (
    <span className={`required-badge ${required ? "required" : "optional"}`}>
      {required ? "Required" : "Optional"}
    </span>
  );
}
