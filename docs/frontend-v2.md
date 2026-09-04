# EVA frontend V2

Phase 10 introduces `frontend-v2/` beside the existing Create React App in `frontend/`. The classic application remains the production rollback target until every feature reaches parity.

## Stack

- Next.js App Router and strict TypeScript
- Tailwind CSS with a shadcn-compatible component setup
- TanStack Query for API/server state
- Zustand for the short-lived in-memory access session only
- Lucide icons and responsive, keyboard-focusable controls

## Run locally

Copy `frontend-v2/.env.example` to `frontend-v2/.env.local`, start the modular backend, and then run:

```powershell
cd frontend-v2
npm install
npm run dev
```

`NEXT_PUBLIC_EVA_API_URL` configures the backend without a hardcoded application endpoint. `NEXT_PUBLIC_LEGACY_APP_URL` points users to classic EVA for features still migrating.

## Authentication

The frontend holds the short-lived access token only in memory. A rotating refresh token is an HTTP-only, SameSite cookie. Page reloads restore the session through `/api/v1/auth/refresh`; logout revokes the refresh-token family. The V2 login works with UUID users already migrated to PostgreSQL. The legacy login remains unchanged.

## Current parity

The central chat, new-conversation flow, and history navigation use `/api/v1` end to end. Translate, Study, Documents, Voice, Call Assistant, and Settings have responsive route shells and link back to classic EVA until their V2 interfaces pass parity review. This keeps partially migrated controls from pretending to be complete.

## Deployment and rollback

Deploy `frontend-v2` independently and route preview traffic to it. Keep `frontend` deployed during the parity window. Rollback is a routing change back to the CRA deployment; no legacy frontend files are removed or rewritten.
