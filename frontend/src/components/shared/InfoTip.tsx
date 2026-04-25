import React, { useState, useRef, useEffect } from 'react';

interface InfoTipProps {
  text: string;
  label?: string;
}

const ACRONYM_GLOSSARY: Record<string, string> = {
  CVE: 'Common Vulnerabilities and Exposures — a public catalog of known software security flaws, each with a unique ID.',
  KEV: 'Known Exploited Vulnerabilities — CISA’s list of CVEs that attackers are actively exploiting in the wild.',
  CVSS: 'Common Vulnerability Scoring System — a 0–10 severity score for a CVE. Higher = more dangerous.',
  SMB: 'Small and Medium-sized Business.',
  IC3: 'FBI Internet Crime Complaint Center — collects reports of cybercrime and publishes annual loss statistics.',
  CISA: 'Cybersecurity and Infrastructure Security Agency — the U.S. federal agency that publishes KEV and other advisories.',
  NVD: 'National Vulnerability Database — NIST’s detailed feed of CVE data with severity scoring.',
  BEA: 'Bureau of Economic Analysis — source of the economic indicators used to benchmark industry risk.',
  MFA: 'Multi-Factor Authentication — requires a second proof of identity (e.g., a code) in addition to a password.',
  SSO: 'Single Sign-On — one login that grants access to multiple applications.',
  EDR: 'Endpoint Detection and Response — software that monitors laptops/servers for malicious activity.',
  SIEM: 'Security Information and Event Management — a central system that collects and analyzes security logs.',
  PII: 'Personally Identifiable Information — data that can identify a specific person (name, SSN, email, etc.).',
  NIST: 'National Institute of Standards and Technology — publishes widely used cybersecurity frameworks.',
};

export const getAcronymDefinition = (acronym: string): string | undefined =>
  ACRONYM_GLOSSARY[acronym.toUpperCase()];

const InfoTip: React.FC<InfoTipProps> = ({ text, label }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: Event) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span
      ref={ref}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        pointerEvents: 'auto',
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={label ? `Info: ${label}` : `Info: ${text}`}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        style={{
          marginLeft: 4,
          cursor: 'help',
          color: 'var(--text-muted)',
          fontSize: '0.85em',
          userSelect: 'none',
          background: 'transparent',
          border: 'none',
          padding: 0,
          lineHeight: 1,
          pointerEvents: 'auto',
        }}
      >
        ⓘ
      </button>
      {open && (
        <span
          role="tooltip"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 1000,
            minWidth: 180,
            maxWidth: 280,
            padding: '8px 10px',
            background: 'var(--card-bg)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            fontSize: '0.8rem',
            lineHeight: 1.4,
            fontWeight: 400,
            whiteSpace: 'normal',
            textAlign: 'left',
            pointerEvents: 'none',
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
};

export default InfoTip;
