# Mentor Feedback Remediation Plan

**Source:** Mentor critique, April 2026
**Status snapshot:** Several items are partially in-flight on the uncommitted working tree (LandingPage.tsx, InfoTip.tsx, OrgProfilePage sync logic). This plan confirms what's done, what's partial, and what still needs work before presentation.

---

## Goal
Address mentor feedback to raise presentation-readiness, focusing on first-impression polish (landing page, light-mode contrast, acronym clarity) and fixing the two functional bugs called out (SMB Advisor dropdown staleness, Findings/AI Briefing load errors).

## Scope
Frontend only. No backend or data-model changes required.

## Constraints
- No new dependencies without approval.
- Keep changes task-scoped — do not refactor unrelated files.
- Preserve dark-mode contrast, which mentor praised.

---

## Item-by-item assessment and actions

### 1. Logged-out / marketing landing page — **PARTIAL (uncommitted)**
**Current state:** [frontend/src/pages/LandingPage.tsx](../frontend/src/pages/LandingPage.tsx) exists as an untracked file with hero, stats, feature cards, CTAs to `/login` and `/signup`. Routed at `/` in [App.tsx:18](../frontend/src/App.tsx#L18).

**Actions:**
- [ ] Populate stats section with real "big numbers" (CVE count, KEV count, IC3 incidents ingested, vendor catalog size) — pull from `/api/v1/stats` or hardcode current totals for demo.
- [ ] Add a one-sentence value prop above the hero ("What this is"): "Threat intelligence tailored to your small business's tech stack."
- [ ] Verify logged-out users hitting protected routes redirect to landing (not login) for marketing value.
- [ ] Commit the file.

### 2. SMB Risk Advisor — dropdown bug + action plan position — **FIX REQUIRED**
**Current state:** [SmBAdvisorTab.tsx:779-908](../frontend/src/components/tabs/SmBAdvisorTab.tsx#L779-L908). Per investigation, `selectedSector`/`selectedState` are populated from org profile auto-fill; the Action Plan Card is already at line 884 before the Risk Score/Grade cards. **However, the mentor reports visible dropdowns at the top of the page that don't propagate on change.** This means either (a) there are editable dropdowns not captured in my read, or (b) read-only display elements that *look* like dropdowns.

**Actions:**
- [ ] Re-read SmBAdvisorTab.tsx top section (lines 700–830) and confirm whether the industry/state UI elements are `<select>` or display-only. If `<select>`, either:
  - **Preferred:** remove them (mentor's recommendation — "state and industry won't change often, better to remove"), OR
  - Wire `onChange` to refetch all dependent data (score, grade, threats, cost, state risk) and verify every card updates.
- [ ] Confirm Action Plan Card is visually the first card after the header/profile context (already true per code order line 884 — verify rendered output matches).
- [ ] Add a "Change in Org Profile →" link in the profile-context card so users know where to edit.

### 3. Security Findings page load error — **INVESTIGATE**
**Current state:** [FindingsTab.tsx:84-187](../frontend/src/components/tabs/FindingsTab.tsx#L84-L187) has error handling with retry + setup-checklist fallback. No direct Gemini call in this file. Mentor saw an error on load — likely a transient backend error or an uncovered case in `Promise.allSettled`.

**Actions:**
- [ ] Reproduce with a test account in the same state as the mentor's (check what org profile fields were set).
- [ ] Check browser console + network tab for the actual failing endpoint.
- [ ] If Gemini-backed (AI enrichment), ensure error is non-fatal and the page renders CVE data regardless.
- [ ] Add a clearer empty/error state that distinguishes "no findings yet" from "API failed".

### 4. AI Risk Briefing load error — **INVESTIGATE**
**Current state:** [AISummaryTab.tsx:163-207](../frontend/src/components/tabs/AISummaryTab.tsx#L163-L207) has three error paths (incomplete setup, disabled feature, generic). Gemini call is backend-driven.

**Actions:**
- [ ] Reproduce and capture backend logs — likely Gemini rate limit, auth, or payload error.
- [ ] Confirm the "disabled feature" path surfaces a helpful message (not a raw error) when the org hasn't enabled AI.
- [ ] If Gemini is flaky, add a cached "last successful briefing" fallback so the tab never appears fully broken on demo day.

### 5. Acronym tooltips — **PARTIAL (uncommitted)**
**Current state:** [InfoTip.tsx](../frontend/src/components/shared/InfoTip.tsx) exists (untracked). Used for CVE, KEV, CVSS, SMB across tabs.

**Actions:**
- [ ] Audit first-render text of every page for acronyms and jargon. Missing coverage to add: **IC3**, **KEV** (first appearance per page), **CISA**, **NVD**, **BEA**, **MFA**, **SSO**, **EDR**, **SIEM**, **NIST CSF** (if referenced), **PII**.
- [ ] Upgrade InfoTip from `title` attribute (native browser tooltip, slow + ugly) to a styled hover/focus popover — still no new deps, use CSS.
- [ ] Commit InfoTip.tsx.

### 6. Vendor Alerts ↔ Org Profile tech stack sync — **PARTIAL**
**Current state:** [OrgProfilePage.tsx:587-597](../frontend/src/pages/OrgProfilePage.tsx#L587-L597) auto-adds checked cloud providers into the vendor tech stack on save (one-way). Mentor's complaint: checking a vendor on the Vendor Alerts page doesn't reflect in Settings.

**Actions:**
- [ ] Decide direction: is [VendorAlertsTab.tsx](../frontend/src/components/tabs/VendorAlertsTab.tsx) read-only (alerts for vendors already in stack), or does it allow adding vendors? Confirm the mentor's expectation.
- [ ] If Vendor Alerts lets users "check" vendors, make that action write back to the org profile tech stack via the same endpoint that OrgProfilePage uses.
- [ ] Alternatively, remove the check-boxes on Vendor Alerts and make it purely a read view sourced from profile — with a clear "Manage vendors in Settings →" link.

### 7. Light-mode contrast — **FIX REQUIRED**
**Current state:** [Dashboard.css:2-29](../frontend/src/Dashboard.css#L2-L29). Issues:
- `--text-muted: #4b5563` on white → **5.2:1** (fails WCAG AA normal text).
- `--warn-bg: #fffbeb` with `--warn-text: #92400e` → **4.2:1** (fails AA).

**Actions:**
- [ ] Darken `--text-muted` to `#374151` (≈8.9:1) or `#4b5563`→`#3f4652`.
- [ ] Darken `--warn-text` to `#7c2d12` (≈5.9:1) or darken warn-bg.
- [ ] Spot-check secondary text across Findings, Vendor Alerts, and Org Profile in light mode; run a contrast-check extension (e.g. axe DevTools in browser — no code dep).
- [ ] Do not touch dark-mode tokens.

---

## Verification
- [ ] Manual QA pass in both light and dark mode on: Landing (logged-out), Dashboard tabs (Findings, AI Summary, Vendor Alerts, SMB Advisor), Org Profile.
- [ ] `cd frontend && npm run lint && npm run build` clean.
- [ ] `cd frontend && npm run test` green.
- [ ] Record a 2-min loom of the SMB Advisor page flow to send back to mentor.

## Risks
- **Gemini-backed errors (items 3, 4)** may be environmental — might not reproduce locally. Mitigation: deploy to Render staging and test against production-like config before presentation.
- Removing SMB Advisor dropdowns is a UX change — confirm with team that profile-edit redirection is acceptable.
- Contrast token changes could subtly shift visuals across many pages; review each tab after the change.

## Phased rollout
1. **Phase 1 (blocking for presentation):** Items 2, 3, 4 (functional bugs) + commit items 1 and 5.
2. **Phase 2 (polish):** Items 6, 7 (sync + contrast).
3. **Phase 3 (nice-to-have):** Populate landing stats from live API; upgrade InfoTip to styled popover.

## Existing branch / PR findings
Current branch `main` has uncommitted work covering items 1 and 5. No open PRs found for the remaining items. Last merged PR (#78) was dashboard tab enhancements — unrelated.

## Follow-up
Once Phase 1 lands, send mentor a short note listing what was addressed so they can do the offered second-pass review before presentation day.
