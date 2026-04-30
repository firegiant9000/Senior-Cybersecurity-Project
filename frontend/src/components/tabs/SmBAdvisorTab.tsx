import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const INDUSTRY_LABEL_TO_SECTOR: Record<string, string> = {
  'Finance & Insurance': 'Finance',
  'Healthcare': 'Healthcare',
  'Tech & Software': 'Technology',
  'Government': 'Government',
  'Retail & E-Commerce': 'Retail',
  'Education': 'Education',
  'Manufacturing': 'Manufacturing',
  'Professional Services': 'Professional Services',
};
import { Link } from 'react-router-dom';
import { useUserContext } from '../../context/UserContext';
import './SmBAdvisorTab.css';
import DisclaimerBanner from '../shared/DisclaimerBanner';
import InfoTip from '../shared/InfoTip';
import ConfidenceBadge, { type ConfidenceTier } from '../shared/ConfidenceBadge';
import { SMB_ADVISOR_DISCLAIMER } from '../../constants/disclaimers';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  fetchIndustryRisk,
  fetchAttackTypes,
  fetchSectorAttackMatrix,
  fetchGeographicHeatmap,
  type IndustryRiskProfile,
  type AttackTypeStats,
  type SectorAttackCombination,
  type GeographicThreat,
} from '../../api/dashboardSummary';
import { fetchSmbRiskScore, type SmbRiskScore } from '../../api/smbRiskScore';
import WidgetSkeleton from '../shared/WidgetSkeleton';

// ─── Constants ────────────────────────────────────────────────────────────────

const STATE_NAMES: Record<string, string> = {
  AL:'Alabama', AK:'Alaska', AZ:'Arizona', AR:'Arkansas', CA:'California',
  CO:'Colorado', CT:'Connecticut', DE:'Delaware', FL:'Florida', GA:'Georgia',
  HI:'Hawaii', ID:'Idaho', IL:'Illinois', IN:'Indiana', IA:'Iowa',
  KS:'Kansas', KY:'Kentucky', LA:'Louisiana', ME:'Maine', MD:'Maryland',
  MA:'Massachusetts', MI:'Michigan', MN:'Minnesota', MS:'Mississippi', MO:'Missouri',
  MT:'Montana', NE:'Nebraska', NV:'Nevada', NH:'New Hampshire', NJ:'New Jersey',
  NM:'New Mexico', NY:'New York', NC:'North Carolina', ND:'North Dakota', OH:'Ohio',
  OK:'Oklahoma', OR:'Oregon', PA:'Pennsylvania', RI:'Rhode Island', SC:'South Carolina',
  SD:'South Dakota', TN:'Tennessee', TX:'Texas', UT:'Utah', VT:'Vermont',
  VA:'Virginia', WA:'Washington', WV:'West Virginia', WI:'Wisconsin', WY:'Wyoming', DC:'Washington D.C.',
};

// Threat-specific plain-English action recommendations
const THREAT_ACTIONS: Record<string, { icon: string; actions: string[] }> = {
  'Business Email Compromise': {
    icon: '📧',
    actions: [
      'Enable multi-factor authentication (MFA) on all email accounts today',
      'Train staff to verify any unusual financial request by phone — never email alone',
      'Ask your IT provider to set up email authentication (SPF/DKIM/DMARC)',
    ],
  },
  'Ransomware': {
    icon: '🔒',
    actions: [
      'Back up all business data daily to a secure, separate location (cloud + offline)',
      'Keep all computers and software up to date — especially operating systems',
      'Limit employee access to only the files and systems they actually need',
    ],
  },
  'Phishing/Vishing/Smishing/Pharming': {
    icon: '🎣',
    actions: [
      'Run a short phishing awareness training for all employees every quarter',
      'Enable email spam and phishing filter on your business email',
      "Teach staff: never click links in unexpected emails — go directly to the website",
    ],
  },
  'Personal Data Breach': {
    icon: '🛡️',
    actions: [
      'Encrypt any files or databases containing customer personal information',
      'Use strong, unique passwords for every account and consider a business password manager',
      'Create a simple incident response plan so you know what to do if data is leaked',
    ],
  },
  'Non-Payment/Non-Delivery': {
    icon: '📦',
    actions: [
      'Verify new vendors or customers before large transactions',
      'Use traceable, verified payment methods and keep records of all transactions',
    ],
  },
  'Identity Theft': {
    icon: '🪪',
    actions: [
      'Monitor your business bank and credit accounts regularly for unusual activity',
      'Use strong passwords and set up alerts on all financial accounts',
    ],
  },
  'Investment Fraud': {
    icon: '📈',
    actions: [
      'Be very cautious of investment opportunities via social media or cold calls',
      'Independently verify any financial advisor or investment platform before engaging',
    ],
  },
  'Tech Support Fraud': {
    icon: '💻',
    actions: [
      'Educate staff: legitimate tech companies never call you unsolicited about a problem',
      'Never grant remote access to your computer unless you initiated the support request',
    ],
  },
  'Romance or Confidence Fraud': {
    icon: '💔',
    actions: [
      'Be suspicious of anyone you have only met online asking for money or gift cards',
      'Train staff to recognize social engineering tactics',
    ],
  },
  'Extortion': {
    icon: '⚠️',
    actions: [
      'Do not pay — contact the FBI IC3 or local law enforcement immediately',
      'Preserve all communications as evidence before responding',
    ],
  },
};

const GENERAL_ACTIONS = [
  { icon: '🏥', text: 'Get cyber liability insurance — many SMB policies cost under $1,500/year and cover incident response' },
  { icon: '📋', text: 'Create a simple incident response plan so your team knows what to do in the first hour of an attack' },
  { icon: '🔄', text: 'Test your data backups monthly to confirm they actually work before you need them' },
  { icon: '👤', text: 'Designate one person responsible for cybersecurity in your business, even if it is you' },
];

const SECURITY_CONTROL_MATCHES: [pattern: string, controlKey: string][] = [
  ['multi-factor authentication', 'mfa_enabled'],
  ['email authentication (SPF', 'email_filtering'],
  ['phishing awareness training', 'phishing_training'],
  ['email spam and phishing filter', 'email_filtering'],
  ['computers and software up to date', 'auto_patching'],
  ['Encrypt any files or databases', 'devices_encrypted'],
  ['strong, unique passwords', 'password_policy'],
  ['EDR/antivirus', 'edr_deployed'],
];

function isControlEnabled(controls: Record<string, string>, key: string): boolean {
  const val = controls[key];
  return !!val && val !== 'no' && val !== 'false' && val !== '0' && val !== 'unsure';
}

function getOrgFilledKeys(
  actions: Array<{ key: string; text: string }>,
  controls: Record<string, string> | null,
): Set<string> {
  if (!controls) return new Set();
  const filled = new Set<string>();
  for (const action of actions) {
    for (const [pattern, controlKey] of SECURITY_CONTROL_MATCHES) {
      if (action.text.toLowerCase().includes(pattern.toLowerCase()) && isControlEnabled(controls, controlKey)) {
        filled.add(action.key);
        break;
      }
    }
  }
  return filled;
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface AdvisorData {
  industryRisk: IndustryRiskProfile[];
  attackTypes: AttackTypeStats[];
  sectorAttackMatrix: SectorAttackCombination[];
  geographicThreats: GeographicThreat[];
}

interface RiskGrade {
  letter: string;
  label: string;
  color: string;
  bgColor: string;
  description: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtMoney(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${v.toLocaleString()}`;
}

function fmtMoneyFull(v: number): string {
  return `$${Math.round(v).toLocaleString()}`;
}

function calcRiskGrade(
  sector: IndustryRiskProfile | undefined,
  allSectors: IndustryRiskProfile[],
): RiskGrade {
  if (!sector || allSectors.length === 0) {
    return { letter: '?', label: 'Unknown', color: '#9e9e9e', bgColor: '#f5f5f5', description: 'Select your industry to see your risk grade.' };
  }

  // Sort by avg_loss DESC to rank sectors
  const sorted = [...allSectors].sort((a, b) => b.avg_loss_per_incident - a.avg_loss_per_incident);
  const rank = sorted.findIndex(s => s.sector === sector.sector);
  const pct = rank / sorted.length; // 0 = worst, 1 = best

  if (pct < 0.20) return {
    letter: 'F',
    label: 'Critical Risk',
    color: '#fff',
    bgColor: '#b71c1c',
    description: 'Your industry is among the hardest hit. Attackers actively target businesses like yours — treat cybersecurity as a top business priority right now.',
  };
  if (pct < 0.40) return {
    letter: 'D',
    label: 'High Risk',
    color: '#fff',
    bgColor: '#d32f2f',
    description: 'Your industry faces significantly above-average financial losses from cyber incidents. Immediate action on the basics can reduce your exposure.',
  };
  if (pct < 0.60) return {
    letter: 'C',
    label: 'Elevated Risk',
    color: '#fff',
    bgColor: '#f57c00',
    description: 'Your industry sees moderate-to-high cybercrime activity. Proactive security measures will meaningfully lower your risk.',
  };
  if (pct < 0.80) return {
    letter: 'B',
    label: 'Moderate Risk',
    color: '#333',
    bgColor: '#fbc02d',
    description: 'Your industry is below average in terms of losses, but no business is immune. Keeping up basic security practices keeps you protected.',
  };
  return {
    letter: 'A',
    label: 'Lower Risk',
    color: '#fff',
    bgColor: '#388e3c',
    description: "Your industry sees lower-than-average cybercrime losses. Maintain good security habits — risk can grow quickly if you let your guard down.",
  };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

function useAdvisorData() {
  const [data, setData] = useState<AdvisorData>({
    industryRisk: [],
    attackTypes: [],
    sectorAttackMatrix: [],
    geographicThreats: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey(k => k + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    setLoading(true);
    setError(null);

    Promise.allSettled([
      fetchIndustryRisk(signal),
      fetchAttackTypes(signal),
      fetchSectorAttackMatrix(signal),
      fetchGeographicHeatmap(signal),
    ]).then(([industryR, attackR, matrixR, geoR]) => {
      if (signal.aborted) return;
      const errs: string[] = [];
      const val = <T,>(r: PromiseSettledResult<T>, fallback: T) => {
        if (r.status === 'rejected') {
          if (!(r.reason instanceof Error && r.reason.name === 'AbortError')) {
            errs.push(r.reason instanceof Error ? r.reason.message : String(r.reason));
          }
          return fallback;
        }
        return r.value;
      };

      setData({
        industryRisk: val(industryR, { items: [], year: null }).items,
        attackTypes: val(attackR, { items: [], year: null }).items,
        sectorAttackMatrix: val(matrixR, { items: [], year: null }).items,
        geographicThreats: val(geoR, { items: [], year: null }).items,
      });
      if (errs.length > 0) setError(`Some data could not be loaded: ${errs.slice(0, 2).join('; ')}`);
    }).finally(() => { if (!signal.aborted) setLoading(false); });

    return () => controller.abort();
  }, [refreshKey]);

  return { data, loading, error, refresh };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function RiskGradeCard({ grade, sectorProfile, loading }: {
  grade: RiskGrade;
  sectorProfile: IndustryRiskProfile | undefined;
  loading: boolean;
}) {
  return (
    <div className="card smb-risk-grade-card">
      <div className="smb-grade-left">
        <div className="smb-grade-circle" style={{ background: grade.bgColor, color: grade.color }}>
          {loading ? '…' : grade.letter}
        </div>
        <div>
          <div className="smb-grade-label" style={{ color: grade.bgColor }}>{loading ? '—' : grade.label}</div>
          <div className="smb-grade-desc">{loading ? 'Loading your risk profile…' : grade.description}</div>
        </div>
      </div>
      {sectorProfile && !loading && (
        <div className="smb-grade-stats">
          <div className="smb-stat-item">
            <span className="smb-stat-value">{fmtMoney(sectorProfile.avg_loss_per_incident)}</span>
            <span className="smb-stat-label">Avg loss per incident</span>
          </div>
          <div className="smb-stat-item">
            <span className="smb-stat-value">{sectorProfile.complaint_count.toLocaleString()}</span>
            <span className="smb-stat-label">Reported incidents</span>
          </div>
          <div className="smb-stat-item">
            <span className="smb-stat-value">{fmtMoney(sectorProfile.total_loss)}</span>
            <span className="smb-stat-label">Total losses on record</span>
          </div>
        </div>
      )}
    </div>
  );
}

function TopThreatsCard({ threats, loading }: {
  threats: SectorAttackCombination[];
  loading: boolean;
}) {
  const top5 = threats.slice(0, 5);

  return (
    <div className="card smb-threats-card">
      <h3 className="smb-section-title"> Top Threats Targeting Your Industry</h3>
      <p className="smb-section-sub">Based on FBI crime complaint data — ranked by financial impact</p>
      {loading ? (
        <WidgetSkeleton variant="chart" />
      ) : top5.length === 0 ? (
        <p className="smb-empty">Select your industry to see specific threats.</p>
      ) : (
        <div className="smb-threats-list">
          {top5.map((t, i) => {
            const info = THREAT_ACTIONS[t.attack_type];
            const icon = info?.icon ?? '🔴';
            const maxLoss = top5[0].total_loss;
            const barPct = maxLoss > 0 ? (t.total_loss / maxLoss) * 100 : 0;
            return (
              <div key={t.attack_type} className="smb-threat-row">
                <div className="smb-threat-header">
                  <span className="smb-threat-rank">#{i + 1}</span>
                  <span className="smb-threat-icon">{icon}</span>
                  <span className="smb-threat-name">{t.attack_type}</span>
                  <span className="smb-threat-loss">{fmtMoney(t.avg_loss_per_incident)} avg loss</span>
                </div>
                <div className="smb-threat-bar-bg">
                  <div className="smb-threat-bar-fill" style={{ width: `${barPct}%` }} />
                </div>
                <div className="smb-threat-meta">
                  {t.complaint_count.toLocaleString()} incidents reported &nbsp;·&nbsp; {fmtMoney(t.total_loss)} total losses
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CostEstimateCard({ sectorProfile, allSectors, loading }: {
  sectorProfile: IndustryRiskProfile | undefined;
  allSectors: IndustryRiskProfile[];
  loading: boolean;
}) {
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    setShowMethodology(false);
  }, [sectorProfile?.sector]);

  const nationalAvg = useMemo(() => {
    if (allSectors.length === 0) return 0;
    return allSectors.reduce((s, x) => s + x.avg_loss_per_incident, 0) / allSectors.length;
  }, [allSectors]);

  const low = sectorProfile ? sectorProfile.avg_loss_per_incident * 0.5 : 0;
  const high = sectorProfile ? sectorProfile.avg_loss_per_incident * 2.0 : 0;

  const tier: ConfidenceTier = !sectorProfile
    ? 'Low'
    : sectorProfile.complaint_count >= 1000
      ? 'High'
      : sectorProfile.complaint_count >= 100
        ? 'Medium'
        : 'Low';

  return (
    <div className="card smb-cost-card">
      <h3 className="smb-section-title"> What Could This Cost Your Business?</h3>
      <p className="smb-section-sub">Estimated financial impact based on real incident data for your industry</p>
      {loading ? (
        <WidgetSkeleton />
      ) : !sectorProfile ? (
        <p className="smb-empty">Select your industry to see cost estimates.</p>
      ) : (
        <>
          <div className="smb-cost-range">
            <div className="smb-cost-band smb-cost-low">
              <div className="smb-cost-amount">{fmtMoneyFull(low)}</div>
              <div className="smb-cost-band-label">Low-end estimate</div>
            </div>
            <div className="smb-cost-arrow">→</div>
            <div className="smb-cost-band smb-cost-mid">
              <div className="smb-cost-amount">{fmtMoneyFull(sectorProfile.avg_loss_per_incident)}</div>
              <div className="smb-cost-band-label">Typical loss</div>
            </div>
            <div className="smb-cost-arrow">→</div>
            <div className="smb-cost-band smb-cost-high">
              <div className="smb-cost-amount">{fmtMoneyFull(high)}</div>
              <div className="smb-cost-band-label">Severe incident</div>
            </div>
          </div>
          <div className="smb-cost-context">
            <p>
              The national average loss across all industries is <strong>{fmtMoneyFull(nationalAvg)}</strong> per incident.
              {sectorProfile.avg_loss_per_incident > nationalAvg
                ? ` Your industry's average of ${fmtMoneyFull(sectorProfile.avg_loss_per_incident)} is ${((sectorProfile.avg_loss_per_incident / nationalAvg - 1) * 100).toFixed(0)}% above the national average.`
                : ` Your industry's average of ${fmtMoneyFull(sectorProfile.avg_loss_per_incident)} is below the national average — but losses can still be devastating for a small business.`
              }
            </p>
            <p className="smb-cost-note">
              These figures come from FBI IC3<InfoTip text="IC3 (Internet Crime Complaint Center) — FBI's cybercrime reporting database" /> complaint data and represent direct financial losses. Recovery costs, downtime, and reputational damage can add significantly more.
            </p>
            <div className="smb-cost-meta">
              <ConfidenceBadge tier={tier} context="smb" />
              <span className="smb-cost-meta-sample">
                Based on {sectorProfile.complaint_count.toLocaleString()} IC3 reports for {sectorProfile.sector}
              </span>
              <button
                type="button"
                className="smb-cost-methodology-toggle"
                onClick={() => setShowMethodology((v) => !v)}
                aria-expanded={showMethodology}
              >
                {showMethodology ? '▲ Hide details' : '▼ How this is calculated'}
              </button>
            </div>
            {showMethodology && (
              <div className="smb-cost-methodology">
                <p>
                  The <strong>typical loss</strong> is the average loss per IC3-reported incident for{' '}
                  <strong>{sectorProfile.sector}</strong>. The <strong>low-end</strong> and{' '}
                  <strong>severe-incident</strong> figures are 0.5× and 2.0× that average — a rough
                  range that brackets most reported incidents in this sector. They are not statistical
                  bounds.
                </p>
                <p>
                  Confidence is based on the number of IC3 reports available for your sector
                  (≥1,000 = High, ≥100 = Medium, fewer = Low).
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function StateRiskCard({ stateCode, stateProfile, allStates, loading }: {
  stateCode: string;
  stateProfile: GeographicThreat | undefined;
  allStates: GeographicThreat[];
  loading: boolean;
}) {
  const top10 = useMemo(
    () => [...allStates].sort((a, b) => b.total_loss - a.total_loss).slice(0, 10),
    [allStates],
  );

  const nationalAvgLoss = useMemo(() => {
    if (allStates.length === 0) return 0;
    return allStates.reduce((s, x) => s + x.total_loss, 0) / allStates.length;
  }, [allStates]);

  const stateRank = useMemo(() => {
    if (!stateProfile) return null;
    const sorted = [...allStates].sort((a, b) => b.total_loss - a.total_loss);
    return sorted.findIndex(s => s.state === stateCode) + 1;
  }, [stateProfile, allStates, stateCode]);

  const chartData = useMemo(() => {
    const data = top10.map(s => ({
      state: s.state,
      loss: s.total_loss,
      isSelected: s.state === stateCode,
    }));
    // If selected state is not in top10, append it
    if (stateCode && stateProfile && !top10.find(s => s.state === stateCode)) {
      data.push({ state: stateCode, loss: stateProfile.total_loss, isSelected: true });
    }
    return data;
  }, [top10, stateCode, stateProfile]);

  return (
    <div className="card smb-state-card">
      <h3 className="smb-section-title">📍 Your State's Risk Level</h3>
      <p className="smb-section-sub">
        {stateCode ? `${STATE_NAMES[stateCode] ?? stateCode} compared to other states` : 'Select your state to see how it compares'}
      </p>
      {loading ? (
        <WidgetSkeleton variant="chart" />
      ) : !stateProfile && stateCode ? (
        <p className="smb-empty">No data available for the selected state.</p>
      ) : !stateCode ? (
        <p className="smb-empty">Select your state above to see local risk data.</p>
      ) : (
        <>
          <div className="smb-state-stats">
            <div className="smb-stat-item">
              <span className="smb-stat-value">#{stateRank ?? '—'}</span>
              <span className="smb-stat-label">State rank (higher = more losses)</span>
            </div>
            <div className="smb-stat-item">
              <span className="smb-stat-value">{stateProfile ? fmtMoney(stateProfile.total_loss) : '—'}</span>
              <span className="smb-stat-label">Total losses in {STATE_NAMES[stateCode] ?? stateCode}</span>
            </div>
            <div className="smb-stat-item">
              <span className="smb-stat-value">{stateProfile ? stateProfile.complaint_count.toLocaleString() : '—'}</span>
              <span className="smb-stat-label">Incidents reported</span>
            </div>
          </div>
          {stateProfile && nationalAvgLoss > 0 && (
            <p className="smb-state-note">
              {stateProfile.total_loss > nationalAvgLoss
                ? `⚠️ ${STATE_NAMES[stateCode] ?? stateCode} sees ${((stateProfile.total_loss / nationalAvgLoss - 1) * 100).toFixed(0)}% more losses than the average state. Being in a high-activity state increases your exposure.`
                : `✅ ${STATE_NAMES[stateCode] ?? stateCode} sees lower-than-average losses compared to other states. Stay vigilant — cybercriminals operate online and don't respect state borders.`
              }
            </p>
          )}
          <div className="smb-state-chart">
            <div className="smb-chart-label">Top states by total losses (your state highlighted)</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="state" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={v => fmtMoney(v as number)} tick={{ fontSize: 10 }} width={48} />
                <Tooltip
                  formatter={(v: unknown) => [fmtMoneyFull(v as number), 'Total Losses']}
                  labelFormatter={(l: unknown) => STATE_NAMES[l as string] ?? String(l)}
                />
                <Bar dataKey="loss" radius={[3, 3, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.state}
                      fill={entry.isSelected ? '#d32f2f' : '#0b1060'}
                      opacity={entry.isSelected ? 1 : 0.55}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

function ActionPlanCard({ topThreats, loading }: {
  topThreats: SectorAttackCombination[];
  loading: boolean;
}) {
  const { organization } = useUserContext();
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [orgApplied, setOrgApplied] = useState(false);
  const toggle = (key: string) => setChecked(prev => ({ ...prev, [key]: !prev[key] }));

  const threatActions = useMemo(() => {
    const seen = new Set<string>();
    const actions: Array<{ key: string; icon: string; text: string; priority: 'high' | 'medium' }> = [];
    topThreats.slice(0, 3).forEach(t => {
      const info = THREAT_ACTIONS[t.attack_type];
      if (info) {
        info.actions.forEach((action, i) => {
          const key = `${t.attack_type}-${i}`;
          if (!seen.has(action)) {
            seen.add(action);
            actions.push({ key, icon: info.icon, text: action, priority: i === 0 ? 'high' : 'medium' });
          }
        });
      }
    });
    return actions;
  }, [topThreats]);

  const allActions = useMemo(() => [
    ...threatActions,
    ...GENERAL_ACTIONS.map((a, i) => ({
      key: `general-${i}`,
      icon: a.icon,
      text: a.text,
      priority: 'medium' as const,
    })),
  ], [threatActions]);

  const orgFilledKeys = useMemo(
    () => getOrgFilledKeys(allActions, organization?.security_controls ?? null),
    [allActions, organization?.security_controls],
  );

  useEffect(() => {
    if (orgApplied || orgFilledKeys.size === 0) return;
    setChecked(prev => {
      const next = { ...prev };
      orgFilledKeys.forEach(k => { if (!(k in next)) next[k] = true; });
      return next;
    });
    setOrgApplied(true);
  }, [orgFilledKeys, orgApplied]);

  const doneCount = allActions.filter(a => checked[a.key]).length;

  return (
    <div className="card smb-action-card">
      <div className="smb-action-header">
        <h3 className="smb-section-title">✅ Your Action Plan</h3>
        <div className="smb-action-progress">
          <div className="smb-progress-bar-bg">
            <div
              className="smb-progress-bar-fill"
              style={{ width: allActions.length > 0 ? `${(doneCount / allActions.length) * 100}%` : '0%' }}
            />
          </div>
          <span className="smb-progress-label">{doneCount}/{allActions.length} completed</span>
        </div>
      </div>
      <p className="smb-section-sub">Prioritized steps tailored to your industry's top threats. Check off items as you complete them.</p>

      {loading ? (
        <WidgetSkeleton />
      ) : (
        <div className="smb-checklist">
          {topThreats.length > 0 && threatActions.length > 0 && (
            <div className="smb-checklist-group">
              <div className="smb-checklist-group-label">Industry-Specific Threats</div>
              {threatActions.map(item => (
                <label key={item.key} className={`smb-check-item ${checked[item.key] ? 'smb-check-done' : ''} ${item.priority === 'high' ? 'smb-check-high' : ''}`}>
                  <input
                    type="checkbox"
                    checked={!!checked[item.key]}
                    onChange={() => toggle(item.key)}
                    className="smb-checkbox"
                  />
                  <span className="smb-check-icon">{item.icon}</span>
                  <span className="smb-check-text">{item.text}</span>
                  {orgFilledKeys.has(item.key) && (
                    <span className="smb-org-badge">From org profile</span>
                  )}
                  {item.priority === 'high' && !checked[item.key] && !orgFilledKeys.has(item.key) && (
                    <span className="smb-priority-badge">Priority</span>
                  )}
                </label>
              ))}
            </div>
          )}
          <div className="smb-checklist-group">
            <div className="smb-checklist-group-label">Every Business Should Do This</div>
            {GENERAL_ACTIONS.map((item, i) => {
              const key = `general-${i}`;
              return (
                <label key={key} className={`smb-check-item ${checked[key] ? 'smb-check-done' : ''}`}>
                  <input
                    type="checkbox"
                    checked={!!checked[key]}
                    onChange={() => toggle(key)}
                    className="smb-checkbox"
                  />
                  <span className="smb-check-icon">{item.icon}</span>
                  <span className="smb-check-text">{item.text}</span>
                  {orgFilledKeys.has(key) && (
                    <span className="smb-org-badge">From org profile</span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Org Risk Score ───────────────────────────────────────────────────────────

function useOrgRiskScore() {
  const [data, setData] = useState<SmbRiskScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchSmbRiskScore(controller.signal)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load org risk score');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  return { data, loading, error };
}

function scoreColor(score: number): string {
  if (score >= 75) return '#b71c1c';
  if (score >= 55) return '#d32f2f';
  if (score >= 40) return '#f57c00';
  if (score >= 25) return '#fbc02d';
  return '#388e3c';
}

function scoreLabel(score: number): string {
  if (score >= 75) return 'Critical';
  if (score >= 55) return 'High';
  if (score >= 40) return 'Elevated';
  if (score >= 25) return 'Moderate';
  return 'Low';
}

function OrgRiskScoreCard() {
  const { data, loading, error } = useOrgRiskScore();

  if (error) {
    // If 404 (no org) or other error, render nothing — org may not be set up yet
    return null;
  }

  return (
    <div className="card smb-org-risk-card">
      <h3 className="smb-section-title">🎯 Your Organization's Risk Score</h3>
      <p className="smb-section-sub">
        Calculated from your org's industry and employee range.{' '}
        <Link to="/org-profile" style={{ color: 'var(--accent)', textDecoration: 'underline', fontSize: 'inherit' }}>
          Update profile
        </Link>{' '}
        to recalculate — this card reflects your saved settings, not the dropdowns above.
      </p>
      {loading ? (
        <WidgetSkeleton />
      ) : !data ? null : (
        <div className="smb-org-risk-body">
          <div className="smb-org-risk-gauge">
            <div
              className="smb-org-risk-score"
              style={{ background: scoreColor(data.score), color: '#fff' }}
            >
              {data.score.toFixed(0)}
            </div>
            <div className="smb-org-risk-label" style={{ color: scoreColor(data.score) }}>
              {scoreLabel(data.score)} Risk
            </div>
            <div className="smb-org-risk-scale">out of 100<InfoTip text="Risk score from 0–100. Higher = more exposure based on your industry and size." /></div>
          </div>

          <div className="smb-org-risk-breakdown">
            {data.breakdown.map(c => (
              <div key={c.name} className="smb-org-risk-component">
                <div className="smb-org-risk-comp-header">
                  <span className="smb-org-risk-comp-name">{c.name}</span>
                  <span className="smb-org-risk-comp-score">{c.score.toFixed(1)}/100</span>
                </div>
                <div className="smb-org-risk-bar-bg">
                  <div
                    className="smb-org-risk-bar-fill"
                    style={{ width: `${c.score}%`, background: scoreColor(c.score) }}
                  />
                </div>
                <div className="smb-org-risk-comp-meta">
                  {(c.weight * 100).toFixed(0)}% weight → contributes {c.weighted_score.toFixed(1)} pts
                </div>
              </div>
            ))}
          </div>

          {data.industry_exposure.sector && (
            <div className="smb-org-risk-top-threats">
              <div className="smb-org-risk-top-label">Top attack types by industry exposure:</div>
              <div className="smb-org-risk-threat-pills">
                {data.industry_exposure.items.slice(0, 3).map(item => (
                  <span key={item.attack_type} className="smb-org-risk-pill">
                    {item.attack_type} ({(item.sector_weight * 100).toFixed(0)}%)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const SmBAdvisorTab: React.FC = () => {
  const { data, loading, error, refresh } = useAdvisorData();
  const { organization } = useUserContext();
  const [selectedSector, setSelectedSector] = useState('');
  const [selectedState, setSelectedState] = useState('');
  const autoFilled = useRef(false);

  // Available sectors from loaded data
  const sectors = useMemo(
    () => [...data.industryRisk].sort((a, b) => a.sector.localeCompare(b.sector)).map(s => s.sector),
    [data.industryRisk],
  );

  const sectorProfile = useMemo(
    () => data.industryRisk.find(r => r.sector === selectedSector),
    [data.industryRisk, selectedSector],
  );

  const sectorThreats = useMemo(
    () =>
      [...data.sectorAttackMatrix]
        .filter(m => m.sector === selectedSector)
        .sort((a, b) => b.total_loss - a.total_loss),
    [data.sectorAttackMatrix, selectedSector],
  );

  const stateProfile = useMemo(
    () => data.geographicThreats.find(g => g.state === selectedState),
    [data.geographicThreats, selectedState],
  );

  const riskGrade = useMemo(
    () => calcRiskGrade(sectorProfile, data.industryRisk),
    [sectorProfile, data.industryRisk],
  );

  // Auto-fill from org profile on first load only
  useEffect(() => {
    if (autoFilled.current || !organization) return;
    if (organization.primary_state && !selectedState) {
      setSelectedState(organization.primary_state);
    }
    if (organization.industry_label && sectors.length > 0) {
      const mapped = INDUSTRY_LABEL_TO_SECTOR[organization.industry_label] ?? organization.industry_label;
      const match = sectors.find(s => s.toLowerCase() === mapped.toLowerCase());
      if (match) {
        setSelectedSector(match);
        autoFilled.current = true;
      }
    }
  }, [organization, sectors, selectedState]);

  return (
    <div className="tab-page smb-advisor-page">
      {/* Header Banner */}
      <div className="smb-hero">
        <div className="smb-hero-text">
          <h2 className="smb-hero-title">SMB Risk Advisor<InfoTip text="SMB (Small and Medium-Sized Business) — typically defined as businesses with fewer than 500 employees" /></h2>
          <p className="smb-hero-sub">
            Personalized cybersecurity insights for small business owners — in plain English, no technical jargon.
          </p>
        </div>
        <button className="overview-refresh-btn" onClick={refresh}>↻ Refresh</button>
      </div>

      {error && (
        <div className="overview-partial-errors">⚠ {error}</div>
      )}

      {/* Profile Context — read-only; driven by saved org profile */}
      <div className="card smb-profile-card">
        <h3 className="smb-profile-title">Your Risk Profile</h3>
        <p className="smb-profile-sub">Risk data below is personalized to your organization's saved industry and state.</p>
        <div className="smb-profile-display">
          <div className="smb-profile-display-item">
            <span className="smb-profile-display-label">🏢 Industry</span>
            <span className="smb-profile-display-value">
              {selectedSector || (loading ? '—' : 'Not set')}
            </span>
          </div>
          <div className="smb-profile-display-item">
            <span className="smb-profile-display-label">📍 State</span>
            <span className="smb-profile-display-value">
              {selectedState ? `${STATE_NAMES[selectedState] ?? selectedState} (${selectedState})` : (loading ? '—' : 'Not set')}
            </span>
          </div>
        </div>
        {(!selectedSector || !selectedState) && !loading && (
          <p className="smb-profile-hint">
            ⚙️ Industry or state not configured.{' '}
            <Link to="/org-profile" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
              Update Organization Profile
            </Link>{' '}
            to unlock your full personalized risk report.
          </p>
        )}
        {selectedSector && selectedState && !loading && (
          <p className="smb-profile-hint" style={{ marginTop: 4 }}>
            <Link to="/org-profile" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
              Update Organization Profile
            </Link>{' '}
            to change your industry or state.
          </p>
        )}
      </div>

      {/* Action Plan — shown early so SMB users see their next steps immediately */}
      <ActionPlanCard topThreats={sectorThreats} loading={loading} />

      {/* Org-level parameterized risk score */}
      <OrgRiskScoreCard />

      {/* Risk Grade */}
      <RiskGradeCard grade={riskGrade} sectorProfile={sectorProfile} loading={loading} />

      {/* Two-column layout for threats + cost */}
      <div className="smb-two-col">
        <TopThreatsCard threats={sectorThreats} loading={loading} />
        <CostEstimateCard sectorProfile={sectorProfile} allSectors={data.industryRisk} loading={loading} />
      </div>

      {/* State Risk */}
      <StateRiskCard
        stateCode={selectedState}
        stateProfile={stateProfile}
        allStates={data.geographicThreats}
        loading={loading}
      />

      {/* Footer disclaimer */}
      <DisclaimerBanner disclaimerBlock={SMB_ADVISOR_DISCLAIMER} variant="full" className="smb-disclaimer" />
    </div>
  );
};

export default SmBAdvisorTab;
