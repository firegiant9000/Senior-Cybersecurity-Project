/**
 * NextStepsCard — post-signup landing nudge.
 *
 * Phase B4 of the Month 2 plan. Replaces the assessment-intake wall: a
 * brand-new org with only name + primary_domain lands on the dashboard
 * and sees this card pointing at the highest-value next actions. The
 * three options mirror the wedge paths called out in
 * docs/month_2_execution_plan.md — upload CSV, connect M365, complete
 * the profile.
 *
 * The card auto-hides once the user has either completed the wizard
 * (`intake_completed_at` is set) or graduated to ENHANCED tier (which
 * means they've already supplied enough data that this nudge is no
 * longer useful).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAssessmentIntake } from "../../hooks/useAssessmentIntake";
import { fetchWithAuth, API_BASE_URL } from "../../api/fetchWithAuth";
import "./NextStepsCard.css";

interface NextStep {
  key: string;
  title: string;
  description: string;
  to: string;
  primary?: boolean;
}

const NEXT_STEPS: NextStep[] = [
  {
    key: "upload_csv",
    title: "Upload CSV inventory",
    description:
      "Drop a list of assets and we'll match them against KEV and NVD in seconds.",
    to: "/dashboard/inventory",
    primary: true,
  },
  {
    key: "connect_m365",
    title: "Connect Microsoft 365",
    description:
      "Pull devices automatically from Intune. Spike — see your devices appear without typing them.",
    to: "/dashboard/integrations",
  },
  {
    key: "complete_profile",
    title: "Complete your profile",
    description:
      "Add industry, controls, and compliance frameworks for richer findings and an AI-written summary.",
    to: "/onboarding",
  },
];

export default function NextStepsCard() {
  const { data: intake } = useAssessmentIntake();
  // Whether the user has marked the intake "done" — read once from the
  // org row. Hidden state because we don't want this card to flicker on
  // every dashboard re-render.
  const [intakeCompletedAt, setIntakeCompletedAt] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetchWithAuth(
          `${API_BASE_URL}/api/v1/auth/me`,
        );
        if (!resp.ok) return;
        const me = await resp.json();
        if (!cancelled && me.org_id) {
          const orgResp = await fetchWithAuth(
            `${API_BASE_URL}/api/v1/organizations/${me.org_id}`,
          );
          if (orgResp.ok) {
            const org = await orgResp.json();
            if (!cancelled) setIntakeCompletedAt(org.intake_completed_at ?? null);
          }
        }
      } catch {
        // Non-fatal — worst case the card stays visible.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Hide once the user has either reached ENHANCED (so they don't need
  // these nudges any more) or explicitly marked intake complete. Also
  // hide if the user dismissed it for this session.
  const hide =
    dismissed ||
    intakeCompletedAt !== null ||
    (intake &&
      (intake.current_tier === "enhanced" ||
        intake.current_tier === "comprehensive"));

  if (hide) return null;

  return (
    <section className="next-steps-card" aria-label="What's next">
      <header className="next-steps-card__header">
        <div>
          <h3 className="next-steps-card__title">What's next?</h3>
          <p className="next-steps-card__subtitle">
            Pick a starting point — each one gets you to a more useful
            dashboard.
          </p>
        </div>
        <button
          type="button"
          className="next-steps-card__dismiss"
          onClick={() => setDismissed(true)}
          aria-label="Hide for now"
        >
          ×
        </button>
      </header>
      <div className="next-steps-card__grid">
        {NEXT_STEPS.map((step) => (
          <Link
            key={step.key}
            to={step.to}
            className={
              "next-steps-card__option" +
              (step.primary ? " next-steps-card__option--primary" : "")
            }
          >
            <div className="next-steps-card__option-title">{step.title}</div>
            <div className="next-steps-card__option-desc">{step.description}</div>
            <div className="next-steps-card__option-cta">Start →</div>
          </Link>
        ))}
      </div>
    </section>
  );
}
