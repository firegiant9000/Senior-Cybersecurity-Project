import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  fetchAssessmentReadiness,
  type AssessmentReadiness,
} from "../api/assessmentReadiness";
import "./AssessmentReadiness.css";

const TIER_LABEL: Record<string, string> = {
  comprehensive: "Comprehensive",
  good: "Good",
  minimal: "Incomplete",
  // Graduated intake tier names (for forward compatibility)
  enhanced: "Enhanced",
  basic: "Basic",
  incomplete: "Incomplete",
};

const TIER_CLASS: Record<string, string> = {
  comprehensive: "readiness-tier--comprehensive",
  good: "readiness-tier--good",
  minimal: "readiness-tier--minimal",
  // Graduated intake tier names
  enhanced: "readiness-tier--good",
  basic: "readiness-tier--minimal",
  incomplete: "readiness-tier--minimal",
};

// Maps readiness key → section element ID on /org-profile (for scroll-to behavior)
const SETTINGS_SECTION_ID: Record<string, string> = {
  vendors: "section-vendors",
  domains: "section-domains",
  uploads: "section-uploads",
  security_controls: "section-security-profile",
  compliance_frameworks: "section-security-profile",
  data_types: "section-security-profile",
};

function handleFix(key: string, navigate: ReturnType<typeof useNavigate>, location: { pathname: string }) {
  const sectionId = SETTINGS_SECTION_ID[key];
  if (location.pathname === "/org-profile" && sectionId) {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    navigate("/org-profile", { state: { scrollTo: sectionId } });
  }
}

interface AssessmentReadinessWidgetProps {
  /** Bump to force a re-fetch (e.g. after a save in the parent page). */
  refreshKey?: number;
}

export default function AssessmentReadinessWidget({ refreshKey = 0 }: AssessmentReadinessWidgetProps = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState<AssessmentReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    fetchAssessmentReadiness(ac.signal)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((err) => {
        if (!ac.signal.aborted)
          setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [refreshKey]);

  if (loading)
    return (
      <div className="readiness-widget readiness-loading">
        Loading readiness...
      </div>
    );
  if (error)
    return <div className="readiness-widget readiness-error">{error}</div>;
  if (!data) return null;

  const requiredItems = data.items.filter((i) => i.required);
  const optionalItems = data.items.filter((i) => !i.required);

  return (
    <div className="readiness-widget">
      <div className="readiness-header">
        <h3>Assessment Readiness</h3>
        <span className={`readiness-tier ${TIER_CLASS[data.tier] ?? ""}`}>
          {TIER_LABEL[data.tier] ?? data.tier}
        </span>
      </div>

      <div className="readiness-bar-container">
        <div
          className="readiness-bar"
          style={{ width: `${data.readiness_pct}%` }}
        />
      </div>
      <p className="readiness-pct-label">{data.readiness_pct}% complete</p>

      <div className="readiness-checklist">
        <h4>Required</h4>
        {requiredItems.map((item) => (
          <div key={item.key} className="readiness-item">
            <span
              className={`readiness-check ${item.complete ? "done" : "pending"}`}
            >
              {item.complete ? "\u2713" : "\u2012"}
            </span>
            <span className="readiness-label">{item.label}</span>
            <span className="readiness-detail">{item.detail}</span>
            {!item.complete && SETTINGS_SECTION_ID[item.key] && (
              <button
                className="readiness-fix-btn"
                onClick={() => handleFix(item.key, navigate, location)}
              >
                Fix
              </button>
            )}
          </div>
        ))}
      </div>

      {optionalItems.length > 0 && (
        <div className="readiness-checklist">
          <h4>Optional</h4>
          {optionalItems.map((item) => (
            <div key={item.key} className="readiness-item">
              <span
                className={`readiness-check ${item.complete ? "done" : "pending"}`}
              >
                {item.complete ? "\u2713" : "\u2012"}
              </span>
              <span className="readiness-label">{item.label}</span>
              <span className="readiness-detail">{item.detail}</span>
              {!item.complete && SETTINGS_SECTION_ID[item.key] && (
                <button
                  className="readiness-fix-btn"
                  onClick={() => handleFix(item.key, navigate, location)}
                >
                  Fix
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {data.next_steps.length > 0 && (
        <div className="readiness-next-steps">
          <h4>Next Steps</h4>
          <ul>
            {data.next_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
