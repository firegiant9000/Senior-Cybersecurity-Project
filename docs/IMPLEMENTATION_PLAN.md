# Implementation Plan: Firebase Auth & CI/CD Pipeline

---

## Manual Steps Still Required

### GitHub Actions Secrets
Add these in **GitHub repo > Settings > Secrets and variables > Actions:**
- `FIREBASE_SERVICE_ACCOUNT` — JSON service account for Firebase deploy
- `VITE_API_BASE_URL` — production backend URL
- `VITE_FIREBASE_API_KEY` — for frontend build
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `RENDER_DEPLOY_HOOK_URL` — when Render service is created
- `BACKEND_URL` — for post-deploy health check

### Render Backend Deployment
- Create a Render service for the backend
- Get the deploy hook URL from Render dashboard > service > Settings
- Add it as `RENDER_DEPLOY_HOOK_URL` secret in GitHub
- ~~Uncomment the `curl` line in `.github/workflows/ci.yml` under `deploy-backend`~~ Already active (2026-09-29). S2 moves the hook secret out of shell interpolation.
- Set the backend start command to: `alembic -c app/db/alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Post-Deploy Health Check
- ~~Uncomment the backend health check step~~ Already active (2026-09-29). It only checks for HTTP 200 against a static `/health`; S4 deepens `/health` to check the database.

---

## Optional Future Enhancements

- **Enforce email verification** — _No longer optional._ The backend now requires a verified email before linking an existing account (PR #192, 2026-09-30; S0 in [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md)). The Firebase Console setting is defence in depth on top of that.
- **Social sign-in providers** — Add Google/GitHub in Firebase Console > Authentication > Sign-in method. The `auth_provider` column will auto-populate from the token.
- **Role-based access control** — Use the `role` column on the User model to restrict certain routes to admin users.

---

## Reference: Potential Issues & Mitigations

### Firebase Auth

1. **Firebase service account key security** — `.gitignore` patterns added: `**/firebase-adminsdk*` and `**/serviceAccountKey*.json`. In production, store as a GitHub Actions secret or environment variable.

2. **Frontend token expiry** — `fetchWithAuth()` calls `user.getIdToken()` before every request. Firebase SDK auto-refreshes expired tokens.

3. **Race condition on first request** — AuthProvider sets `loading = true` initially. ProtectedRoute shows a spinner. No API calls fire until auth resolves.

4. **Testing without Firebase** — `conftest.py` patches `init_firebase`. Test fixtures mock `verify_id_token` with fake decoded tokens.

5. **Docker rebuild after dependency changes** — Run `docker-compose build` to rebuild images after changing `requirements.txt` or `package.json`.

### CI/CD

6. **Frontend env vars at build time** — `VITE_FIREBASE_*` vars passed as `env:` in the workflow build step from GitHub secrets.

7. **Alembic on production DB** — Runs as part of backend start command so it executes on the server with DB access.

8. **Concurrent deploys** — `concurrency: { group: "deploy", cancel-in-progress: true }` ensures only the latest deploy runs.

9. **`alembic.ini` hardcoded URL** — `env.py` reads `DATABASE_URL` from settings and overrides the ini value. Works for production as long as the env var is set.
