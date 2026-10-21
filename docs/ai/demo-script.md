# Demo script: an AI briefing with citations (60 seconds)

A screen capture of a local Hacker Tracker instance. It shows a synthetic organisation's executive briefing, and shows that each notable risk cites the findings it rests on. The recording uses synthetic data only.

## Before recording (about 15 minutes, once)

1. **Local stack:** start it with `make up` and `make migrate` (README, "Development and local setup"), and sign in with a Firebase test account. Use a throwaway account, because the UI shows the signed-in email.
2. **Gemini key:** put `GEMINI_API_KEY` in `backend/.env`, which is what the app's settings read. Never open that file on camera. Leave `GEMINI_MODEL` unset so production uses `gemini-3.6-flash`.
3. **Threat data:** `POST /api/v1/ingest/kev`, then check `GET /api/v1/ingest/status`. The KEV catalogue is what turns vendors into "actively exploited" findings.
4. **Synthetic organisation:** create it through the onboarding wizard.
   - Name `Bayou Bakery LLC (demo)`; industry Hospitality; size 11-50; state LA.
   - Vendors: three products that appear in the CISA KEV catalogue (for example a VPN appliance, a mail server and a remote-access tool), plus one that doesn't.
   - Domain `example.com` (a reserved name, so the DNS checks find no SPF or DMARC record).
   - Security controls: answer about half and leave the rest unknown, so the briefing has data gaps to mention.

   The AI summary needs the profile at **Enhanced** tier or above (`GET /api/v1/organizations/mine/intake`); the route returns 422 below that.
5. **Dry take:** open the **AI Summary** tab once before recording, so a slow first call doesn't land in the take. Each Gemini call costs about half a US cent, and the route allows 5 calls per minute.

## The 60 seconds

| Time | Screen | Say |
|---|---|---|
| 0–8 s | Dashboard for `Bayou Bakery LLC (demo)` | "This is Hacker Tracker, running locally on a made-up bakery. Every finding comes from public threat feeds matched against the bakery's software and domain." |
| 8–20 s | **Findings**: scroll the known-exploited (KEV) findings and the missing-SPF/DMARC finding | "Here are the raw findings: products on CISA's known-exploited list, and an email domain with no spoofing protection." |
| 20–35 s | **AI Summary**: click **Regenerate**, then show the narrative and the notable risks | "Gemini turns that into a plain-English briefing for the owner. The prompt passes the organisation's details and findings as a block of data, never as instructions, so text typed into a profile field can't take over the briefing." |
| 35–50 s | Browser dev tools, **Network**: the `mine/ai-summary?force_refresh=true` response with `notable_risks[0].finding_ids` expanded, next to the matching finding `id` in the `mine/findings` response | "Each risk has to cite the ids of the findings it's based on. A validator drops any risk that cites nothing or cites an id that isn't in the input, so the briefing can't invent a finding." |
| 50–60 s | `docs/ai/case-study.md`, the results table | "On 22 held-out test cases, the hardened version stopped both attacks that got through before: 0 of 10 attack cases succeeded. That's too few to call it statistically proven, and the case study says so." |

## Notes for the take

- **Citations aren't shown in the UI yet.** The dashboard doesn't render `finding_ids`, so the 35–50 s segment uses dev tools. A UI that shows citations is a draft issue in the stage-E PR.
- **The briefing changes each time** (temperature 1.0). Don't script the narrative's exact words; read whatever the take produces.
- **Ids may show up in action steps.** An action step's rationale may include a raw finding id such as "(Finding 1a2b3c4d5e6f)". That's a known open issue (`docs/ai/failures-2026-10-20.md`). Leave it in rather than retaking for a cleaner run.
- **Only quote the held-out before-and-after numbers** from the case study. Don't quote dev-run numbers, and don't say "immune" or "proven".
- **No live injection on camera.** A single run proves nothing either way, and the evaluation already measures it.
- **Before publishing,** check that the capture shows no API key, no `.env` file, no real organisation and no personal email address.
