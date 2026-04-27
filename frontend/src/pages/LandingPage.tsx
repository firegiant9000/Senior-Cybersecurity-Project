import React, { useEffect, useLayoutEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import InfoTip from '../components/shared/InfoTip';
import { getAcronymDefinition } from '../components/shared/InfoTip';
import { API_BASE_URL } from '../api/fetchWithAuth';
import './LandingPage.css';

interface PublicStats {
  cve_total: number;
  kev_total: number;
  ic3_sectors: number;
  industries_supported: number;
}

const FALLBACK_STATS: PublicStats = {
  cve_total: 7000,
  kev_total: 1000,
  ic3_sectors: 16,
  industries_supported: 16,
};

const roundDown = (n: number, step: number) => Math.floor(n / step) * step;

const formatCount = (n: number): string => {
  if (n >= 1000) {
    const rounded = roundDown(n, 1000);
    return `${rounded.toLocaleString()}+`;
  }
  return `${roundDown(n, 10)}+`;
};

const buildStats = (s: PublicStats) => [
  { value: formatCount(s.cve_total), label: 'CVEs tracked' },
  { value: formatCount(s.kev_total), label: 'CISA known-exploited vulnerabilities' },
  { value: `${s.industries_supported}+`, label: 'Industries with targeted threat data' },
  { value: '$4.9M', label: 'Avg healthcare breach cost (FBI IC3)' },
];

const FEATURES = [
  {
    icon: '🛡️',
    title: 'SMB Risk Advisor',
    desc: 'Get a risk grade, cost estimates, and a prioritized action plan tailored to your industry and state — no security expertise required.',
  },
  {
    icon: '🔔',
    title: 'Vendor Alerts',
    desc: "Automatically match your technology stack against CISA's Known Exploited Vulnerabilities catalog and get alerted when your vendors are at risk.",
  },
  {
    icon: '📋',
    title: 'AI Executive Summary',
    desc: 'Generate a plain-language executive briefing from your threat data — ready to share with leadership or board members.',
  },
];

const LandingPage: React.FC = () => {
  const [stats, setStats] = useState<PublicStats>(FALLBACK_STATS);

  useLayoutEffect(() => {
    const prev = document.documentElement.getAttribute('data-theme');
    document.documentElement.setAttribute('data-theme', 'light');
    return () => {
      if (prev) document.documentElement.setAttribute('data-theme', prev);
      else document.documentElement.removeAttribute('data-theme');
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/v1/public/stats`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: PublicStats) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {
        /* fallback already in state */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const statsDisplay = buildStats(stats);

  return (
  <div className="landing-page">
    <header className="landing-header">
      <div className="landing-logo">
        <img src="/logo.png" alt="Hacker Tracker" className="landing-logo-img" />
      </div>
      <nav className="landing-nav">
        <Link to="/login" className="landing-nav-link">Sign In</Link>
        <Link to="/signup" className="landing-nav-btn">Get Started</Link>
      </nav>
    </header>

    <section className="landing-hero">
      <div className="landing-hero-content">
        <p className="landing-hero-tagline">
          Threat intelligence tailored to your small business's tech stack.
        </p>
        <h1 className="landing-hero-title">
          Know Your Cyber Risk<br />Before Attackers Do
        </h1>
        <p className="landing-hero-sub">
          Hacker Tracker aggregates CVE data, CISA advisories, and FBI cybercrime statistics
          to give small and medium businesses a clear picture of their real-world exposure.
        </p>
        <div className="landing-hero-ctas">
          <Link to="/signup" className="landing-cta-primary">Get Started — Free</Link>
          <Link to="/login" className="landing-cta-secondary">Sign In</Link>
        </div>
      </div>
    </section>

    <section className="landing-stats">
      <div className="landing-stats-grid">
        {statsDisplay.map((s) => (
          <div key={s.label} className="landing-stat-card">
            <div className="landing-stat-value">{s.value}</div>
            <div className="landing-stat-label">{s.label}</div>
          </div>
        ))}
      </div>
    </section>

    <section className="landing-features">
      <h2 className="landing-section-title">Everything you need to manage cyber risk</h2>
      <div className="landing-features-grid">
        {FEATURES.map((f) => (
          <div key={f.title} className="landing-feature-card">
            <div className="landing-feature-icon">{f.icon}</div>
            <h3 className="landing-feature-title">{f.title}</h3>
            <p className="landing-feature-desc">{f.desc}</p>
          </div>
        ))}
      </div>
    </section>

    <section className="landing-cta-section">
      <h2 className="landing-cta-title">Ready to see your risk profile?</h2>
      <p className="landing-cta-sub">Set up your organization in minutes. No credit card required.</p>
      <Link to="/signup" className="landing-cta-primary landing-cta-large">Get Started</Link>
    </section>

    <footer className="landing-footer">
      <p className="landing-footer-sources">
        <span>Data sourced from</span>{' '}
        <span className="landing-footer-term">
          CISA<InfoTip text={getAcronymDefinition('CISA')!} label="CISA" />
        </span>{' '}
        <span className="landing-footer-term">
          KEV<InfoTip text={getAcronymDefinition('KEV')!} label="KEV" />
        </span>,{' '}
        <span className="landing-footer-term">
          NVD<InfoTip text={getAcronymDefinition('NVD')!} label="NVD" />
        </span>, FBI{' '}
        <span className="landing-footer-term">
          IC3<InfoTip text={getAcronymDefinition('IC3')!} label="IC3" />
        </span>, and{' '}
        <span className="landing-footer-term">
          BEA<InfoTip text={getAcronymDefinition('BEA')!} label="BEA" />
        </span>
        . For informational purposes only.
      </p>
    </footer>
  </div>
  );
};

export default LandingPage;
