import React, { useState } from 'react';
import type { DisclaimerBlock } from '../../types/disclaimer';
import './DisclaimerBanner.css';

interface Props {
  disclaimerBlock: DisclaimerBlock;
  variant?: 'compact' | 'full';
  className?: string;
}

const DisclaimerBanner: React.FC<Props> = ({
  disclaimerBlock,
  variant = 'full',
  className,
}) => {
  const [expanded, setExpanded] = useState(false);

  if (variant === 'compact') {
    return (
      <div className={`disclaimer-banner disclaimer-banner--compact ${className ?? ''}`}>
        <span className="disclaimer-transparency">{disclaimerBlock.transparency_note}</span>
        <button
          className="disclaimer-expand-toggle"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? 'Hide disclaimer details' : 'Show disclaimer details'}
        >
          {expanded ? '▲ Less' : '▼ More'}
        </button>
        {expanded && (
          <div className="disclaimer-expanded">
            <p className="disclaimer-primary">{disclaimerBlock.primary_text}</p>
            <p className="disclaimer-confidence">{disclaimerBlock.confidence_text}</p>
            <p className="disclaimer-attribution">{disclaimerBlock.data_source_attribution}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`disclaimer-banner disclaimer-banner--full ${className ?? ''}`}>
      <p className="disclaimer-primary">{disclaimerBlock.primary_text}</p>
      <p className="disclaimer-confidence">{disclaimerBlock.confidence_text}</p>
      <p className="disclaimer-attribution">{disclaimerBlock.data_source_attribution}</p>
      <p className="disclaimer-transparency">{disclaimerBlock.transparency_note}</p>
    </div>
  );
};

export default DisclaimerBanner;
