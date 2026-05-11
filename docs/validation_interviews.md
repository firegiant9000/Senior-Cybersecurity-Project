# Hacker Tracker — Validation Interviews

Tracker for Week 0 (and beyond) discovery interviews. One section per interview. Keep raw answers verbatim — synthesize later, do not edit on the way in.

## Summary table

| # | Date | Company | Role | Segment | Pilot interest | Follow-up |
|---|---|---|---|---|---|---|
| 1 | 2026-05-11 | The Common Market | Development / fundraising staff | SMB (non-profit food distribution, ~65 employees) | Yes — open to follow-up | Yes |

---

## Interview 1 — The Common Market

- **Date:** 2026-05-11
- **Interviewer:** Arlo Kharod
- **Interviewee role:** Development / fundraising (not IT)
- **Segment:** SMB, non-IT decision-influencer
- **Company:** The Common Market — food distribution and agriculture; works with farmers, vendors, customers; processes payments to vendors and from customers. Recently delivered emergency food to the City of Baltimore during a COVID-related funding gap.
- **Size:** ~65 employees (majority warehouse workers + drivers)
- **CEO:** "Highlie" (per interviewee — spelling unconfirmed)

### Raw answers

1. **Tell me about your business.** 65 employees, majority warehouse workers and drivers. General distribution and agriculture of food with farmers and vendors. Handles payments to vendors and customers, supports multiple payment methods; trying to migrate everyone to ACH. Interviewee personally does development and fundraising — building programs to convince companies/donors (including pitches to billionaires) to support the org's work, e.g. emergency food delivery in Baltimore as federal funding dries up.

2. **What does a normal week look like?** Prospecting new geographies — currently evaluating 4 for new chapters. Tracking federal money and programs. Writing many reports to funders who have given money.

3. **When tech goes wrong, who do you call?** "Highlie" (CEO) is the primary fixer. Interviewee is also called in to help debug. Others with access also pulled in informally. **No internal IT/debugging system set up. Highlie wants to be in charge of IT but doesn't have the time, so it falls to whoever can get to the issue first.**

4. **Has the business had a tech-related scare?** "Get a lot of phishing emails." NordVPN is established for protection — but that is the extent of the program. **No phishing training program exists.**

5. *(Walk-through of past incident — not separately answered; covered above.)*

6. **Has a customer/vendor/insurance company ever asked you to prove you're secure?** Yes — partners ask whether the company has a VPN and how systems are separated. Also expanding hardware presence (cameras around facilities) in response.

7. **Has anyone sent you a security questionnaire you didn't know how to answer?** "Not really — been sent them but answered them all."

8. **What do you do today to feel safe?** Mark phishing as spam. Run cleaning programs on personal devices. No centralized plan. Mentioned `uBlock Origin`, "disconnect me." Caveat: interviewee called their own setup an abnormal use case.

9. **Do you have someone who handles IT?** 2 people internally, "not divided well."

10. **Do they send you reports / do you read them?** No — "there's a ticketing system but it isn't used."

11. **Monthly tech + security spend (rough)?** "A couple of $2k/month items" — Salesforce, a cloud server, and a "potential Claude system." (See Q16 for annualized figures.)

12. **Would you want a tool that finds known security problems and gives a one-page report?** Yes — would like to know where vulnerabilities are.

13. **What would make you trust a tool like this?** **"Consistency — constant reliable answers."**

14. **If your IT person/MSP gave you a monthly one-page security report, would that change anything? Would you pay more for it?** Yes — would do.

15. **What does your current IT provider send you?** Nothing.

16. **Cybersecurity budget?**
    - **General IT: ~$98,000/year**
    - **Cybersecurity (incl. insurance): ~$60,000/year**
    - Has cyber insurance.

17. **If their bill went up $20–50/month to include monthly security reporting?** "Discussion." (Not an automatic yes, not an automatic no — would require conversation.)

18. **Who else has to approve a new tech expense?** Highlie (the owner) — interviewee says Highlie "would be fine with it."

19. **Anything you wish cybersecurity people understood about small businesses like yours?** No.

20. **OK to come back in a month or two with a rough version?** **Yes.**

### Key signals

**Strongly validates pivot:**
- Real, sized cybersecurity budget — **$60k/year** for a 65-employee non-profit is meaningful. This is not a "we have no budget" segment.
- Already pays for cyber insurance — they are in the "insurance asks them questions" workflow that drives SMB security spend.
- Partners/customers are actively asking about VPN + system separation — external pressure to demonstrate posture exists.
- Internal IT is informal and reactive ("whoever can get to it"). Classic SMB pattern where a monthly report and prioritized to-do list has real value.
- Existing ticketing system is unused — they've already tried lightweight IT process and abandoned it. Whatever we ship needs to be **passive/push** (a report lands in their inbox) rather than **active/pull** (a portal they have to log into).
- Said yes to monthly security report value and yes to follow-up.
- Decision-maker is one person (Highlie). Short approval chain.

**Cautions:**
- Interviewee is not the IT decision-maker and explicitly called their own tech habits "an abnormal use case." Need to interview Highlie directly before treating answers as authoritative on technical environment.
- Price reaction at $20–50/month uplift was "discussion," not enthusiasm. A $5–15/endpoint MSP model on 65 endpoints ($325–975/mo) would be a bigger conversation.
- They have no MSP. The product may serve them direct, not via an MSP — that contradicts the working assumption that **MSP-as-buyer is the wedge**. Worth holding open both paths until more interviews land.

**Quotes worth keeping**

> "Consistency — constant reliable answers."
> — On what would make them trust a security tool. Anchor the reporting/UX design on this.

> "There's a ticketing system but it isn't used."
> — On their current IT tooling. Confirms the push-not-pull design principle.

> "Highlie wants to be in charge but doesn't have time, so it's just whoever can get to it at the time."
> — Describes the SMB IT vacuum that creates the gap the product fills.

### Themes / hypotheses to test in next interviews

1. **Direct-to-SMB may be viable for orgs without an MSP.** Hypothesis to verify: businesses in the 50–150-employee range that have not outsourced IT are open to buying directly. If this holds across 2–3 more interviews, the product has two buyer paths, not one.
2. **Cyber insurance is the upstream forcing function.** Test next: does the insurance carrier itself ask for evidence the report could provide?
3. **"Consistency" is the trust currency, not feature depth.** Worth designing for: same format every month, same metrics, predictable cadence — more important than adding new visualizations.
4. **External-partner security questionnaires are an active pain.** Test: would auto-filling vendor/insurance questionnaires from collected data be more valuable than the report itself?

### Follow-up actions

- [ ] Confirm CEO's name spelling ("Highlie") before any direct outreach.
- [ ] Ask interviewee for an intro to Highlie (the real decision-maker on tech).
- [ ] In ~4 weeks: send a one-page mockup report styled for a food-distribution non-profit; collect first-impression reaction.
- [ ] Add The Common Market to the pilot-prospect list.
- [ ] Specifically ask Highlie about the 2-person internal IT split — what isn't working about it.

---

## Interview template (copy for each new interview)

```
## Interview N — <Company>

- **Date:**
- **Interviewer:**
- **Interviewee role:**
- **Segment:** SMB owner / IT admin / MSP / consultant
- **Company:**
- **Size:**

### Raw answers
1.
2.
...

### Key signals
- Validates pivot:
- Cautions:

### Quotes worth keeping

### Themes / hypotheses to test in next interviews

### Follow-up actions
- [ ]
```
