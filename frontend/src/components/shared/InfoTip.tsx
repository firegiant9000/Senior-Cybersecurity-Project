import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

interface InfoTipProps {
  text: string;
  label?: string;
}

export interface GlossaryEntry {
  term: string;
  definition: string;
}

const TIP_MAX_WIDTH = 280;
const VIEWPORT_MARGIN = 8;
const TIP_GAP = 6;

interface TipCoords {
  top: number;
  left: number;
  placement: 'top' | 'bottom';
}

const GLOSSARY: Record<string, string> = {
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
  ANOMALY:
    'A data point that deviates noticeably from the historical norm. We flag anomalies using z-scores: |z| ≥ 2 = unusual, ≥ 3 = extreme.',
  'VENDOR ALERT':
    'A newly published CVE affecting one of the technology vendors in your stack. Each alert links the CVE to the affected vendor so you can prioritize patching.',
  'RISK SCORE':
    '0–100 composite score combining vendor exposure, KEV presence, incident frequency, and severity. Higher = more risk. Used to rank assets and findings.',
};

export const getGlossaryDefinition = (term: string): string | undefined =>
  GLOSSARY[term.toUpperCase()];

/** @deprecated Use getGlossaryDefinition. Kept for compatibility with existing acronym-only call sites. */
export const getAcronymDefinition = getGlossaryDefinition;

export const getGlossaryEntries = (): GlossaryEntry[] =>
  Object.entries(GLOSSARY)
    .map(([term, definition]) => ({ term, definition }))
    .sort((a, b) => a.term.localeCompare(b.term));

const InfoTip: React.FC<InfoTipProps> = ({ text, label }) => {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<TipCoords | null>(null);
  const ref = useRef<HTMLElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const recompute = useCallback(() => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const placement: 'top' | 'bottom' = rect.top > 140 ? 'top' : 'bottom';
    const top = placement === 'top' ? rect.top - TIP_GAP : rect.bottom + TIP_GAP;
    let left = rect.left + rect.width / 2 - TIP_MAX_WIDTH / 2;
    left = Math.max(
      VIEWPORT_MARGIN,
      Math.min(left, window.innerWidth - TIP_MAX_WIDTH - VIEWPORT_MARGIN),
    );
    setCoords({ top, left, placement });
  }, []);

  useEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    recompute();
    const onDocClick = (e: Event) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('scroll', recompute, true);
    window.addEventListener('resize', recompute);
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('scroll', recompute, true);
      window.removeEventListener('resize', recompute);
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, recompute]);

  return (
    <span
      ref={ref}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        verticalAlign: 'middle',
        pointerEvents: 'auto',
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        ref={buttonRef}
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
          marginLeft: 6,
          cursor: 'help',
          color: open ? '#fff' : 'var(--accent)',
          background: open ? 'var(--accent)' : 'transparent',
          border: '1.5px solid var(--accent)',
          borderRadius: '50%',
          width: 18,
          height: 18,
          minWidth: 18,
          fontSize: 12,
          fontWeight: 700,
          fontFamily: 'Georgia, serif',
          fontStyle: 'italic',
          lineHeight: 1,
          padding: 0,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          userSelect: 'none',
          verticalAlign: 'middle',
          pointerEvents: 'auto',
          transition: 'background 0.15s ease, color 0.15s ease',
        }}
      >
        i
      </button>
      {open && coords && createPortal(
        <span
          role="tooltip"
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
            transform: coords.placement === 'top' ? 'translateY(-100%)' : 'none',
            zIndex: 2000,
            minWidth: 180,
            maxWidth: TIP_MAX_WIDTH,
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
        </span>,
        document.body,
      )}
    </span>
  );
};

export default InfoTip;
