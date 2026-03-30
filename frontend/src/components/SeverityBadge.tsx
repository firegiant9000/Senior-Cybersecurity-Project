import React from 'react';
import { SEVERITY_COLORS } from '../theme';

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
  const color = SEVERITY_COLORS[label as keyof typeof SEVERITY_COLORS] ?? '#9e9e9e';
  return (
    <span
      style={{
        background: color,
        color: '#fff',
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
