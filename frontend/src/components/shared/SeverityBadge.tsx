import React from 'react';
import { SEVERITY_COLORS, SEVERITY_TEXT_COLORS } from '../../theme';

interface SeverityBadgeProps {
  label: string;
  fontSize?: number;
  padding?: string;
}

const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  label,
  fontSize = 11,
  padding = '1px 6px',
}) => {
  const key = (label === 'Moderate'
    ? 'Medium'
    : Object.prototype.hasOwnProperty.call(SEVERITY_COLORS, label) ? label : 'Unknown') as keyof typeof SEVERITY_COLORS;
  const color = SEVERITY_COLORS[key];
  const textColor = SEVERITY_TEXT_COLORS[key];
  return (
    <span
      style={{
        background: color,
        color: textColor,
        borderRadius: 3,
        padding,
        fontSize,
        fontWeight: 700,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
};

export default SeverityBadge;
