# M365 / Entra OAuth Integration Notes (Phase E spike)

Reference for Month 2 Phase E of [month_2_execution_plan.md](month_2_execution_plan.md).
Captures Azure AD app registration, required scopes, redirect URIs, rate-limit
notes, and known edge cases. This is a **spike** — production hardening is a
Month 3 deliverable.

Status: feature-flagged off in production (`ENABLE_M365_INTEGRATION=false`).
Production hardening is DEFERRED as of 2026-09-29; no M365 expansion is
planned (see [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md)).

---

## Azure AD app registration

Register a single multi-tenant app in the Microsoft Entra admin center
(https://entra.microsoft.com → Applications → App registrations → New
registration).

| Field | Value |
|-------|-------|
| Name | Hacker Tracker (Inventory) |
| Supported account types | Accounts in any organizational directory (multi-tenant) |
| Redirect URI (Web) | One per environment — see below |
| Logout redirect URI | n/a for the spike |

Record these in the team password manager (do not commit):

- `M365_CLIENT_ID` — Application (client) ID from the Overview blade
- `M365_CLIENT_SECRET` — generated under Certificates & secrets (12-month
  rotation policy; track expiry)
- `M365_AUTHORITY` — `https://login.microsoftonline.com/common` for
  multi-tenant; per-tenant override `…/{tenant_id}` is supported

### Redirect URIs

Register **all three** in the app registration so dev/staging/prod all work
without re-registering on each promotion:

- Local dev: `http://localhost:8000/api/v1/integrations/m365/callback`
- Staging: `https://staging.<host>/api/v1/integrations/m365/callback`
- Production: `https://<host>/api/v1/integrations/m365/callback`

The backend reads its current redirect URI from `M365_REDIRECT_URI` — keep
this synced to whichever environment the deployment is in.

### Delegated scopes

Requested at consent time. All are delegated (user-context) for the spike;
Month 3 may revisit app-only / client credentials for unattended sync.

- `Device.Read.All` — list devices visible to the signed-in user
- `DeviceManagementManagedDevices.Read.All` — Intune-managed devices
  (hostname, OS, last sync, compliance state)
- `User.Read` — read the signing-in user's profile (used for the consent
  state binding only)
- `offline_access` — required to receive a refresh token

Tenants without Intune licensing will see the second scope succeed at
consent but return an empty `managedDevices` list — handle as
`partial_success` in the scan_run, not failure.

---

## OAuth flow

1. User clicks **Connect M365** on `IntegrationsPage`.
2. Frontend `POST /api/v1/integrations/m365/consent` with the org id.
3. Backend persists a one-time `oauth_states` row (random 32-byte token,
   `purpose='m365_consent'`, `expires_at = now + 10m`) and returns the
   Microsoft authorize URL.
4. User completes Microsoft consent → Microsoft redirects to
   `GET /api/v1/integrations/m365/callback?code=…&state=…`.
5. Backend validates `state` against `oauth_states`, exchanges the code for
   `access_token` + `refresh_token`, encrypts both with Fernet
   (`M365_FERNET_KEY`), and upserts an `integration_credentials` row keyed
   by `(org_id, provider='m365')`.
6. Frontend lands on `IntegrationsPage` with the connection visible.

State tokens are single-use — the callback deletes the row on a successful
match. Expired rows are pruned lazily on the next read; no cron is needed
for the spike.

---

## Sync flow

`POST /api/v1/integrations/m365/sync` (per org, admin role required):

1. Look up `integration_credentials` for the org.
2. Decrypt the refresh token, exchange for a fresh access token.
3. Page through `GET https://graph.microsoft.com/v1.0/deviceManagement/managedDevices`
   (server-side `$top=100`; follow `@odata.nextLink`).
4. For each device, map to the `assets`/`asset_software` schema **once
   Phase A + Phase C3 land**. Until then, the sync stores the raw device
   list in `integration_credentials.last_sync_payload` (JSONB) and returns
   the count + sample. This unblocks the staging demo without depending on
   the inventory model.

The frontend polls `GET /api/v1/integrations/m365` for last-sync status.

---

## Rate limits & edge cases

Documented now so Month 3 productionization doesn't rediscover them:

- **Graph throttling.** Per-app per-tenant. 429 responses include
  `Retry-After`; the client wrapper sleeps that long and retries once.
  More than two consecutive 429s in a single sync = abort with
  `status='partial'` and the captured retry header in
  `metadata.last_retry_after`.
- **Refresh token expiry.** 90-day inactivity window by default; tenants
  with Conditional Access can cut this shorter. On a 401 from the token
  endpoint with `invalid_grant`, mark the credential `status='reauth_needed'`
  and surface a re-connect prompt in the UI.
- **No Intune.** `managedDevices` returns 403 if the signed-in user lacks
  Intune permissions or the tenant has no Intune SKU. Treat as a
  successful sync with `device_count=0` and an explanatory note in the
  scan_run metadata.
- **Guest users.** A guest in tenant A consenting on behalf of tenant B
  results in scoped-down visibility. Document but do not block — the
  consent screen warns the user.
- **Personal Microsoft accounts.** Out of scope for the spike;
  `M365_AUTHORITY` set to `…/common` will still accept them but
  `managedDevices` returns 400. Reject at the callback if
  `tid` (tenant id) claim is the personal-MSA constant
  (`9188040d-6c67-4c5b-b112-36a304b66dad`).

---

## Open questions for Month 3

- Switch to app-only (client credentials + admin consent) so sync can run
  unattended on the scheduler instead of requiring a recent user session?
- Persist scoped tokens per-user vs per-org? Current spike is per-org; a
  team-admin model probably wants per-user with a chosen "owner" for the
  connection.
- Webhook subscriptions (Graph change notifications) for near-real-time
  device updates — viable once we have an HTTPS receiver in prod.
