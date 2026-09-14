# ArthSetu Frontend

React + TypeScript + Vite + Tailwind console for the ArthSetu API.

## Run

```bash
npm install
npm run dev            # http://localhost:5173
```

The dev server proxies `/api/*` to `http://localhost:8000` (the backend), so
start the API first (`python -m uvicorn backend.app.main:app --reload` from the
repo root). Override the target with `VITE_API_TARGET`.

Sign-in is via Firebase Authentication — copy `.env.example` to `.env` and
fill in `VITE_FIREBASE_*` from your Firebase project's Web app config (see
`Docs/API_CONTRACT.md`), or point `VITE_FIREBASE_AUTH_EMULATOR_HOST` at a
locally running Firebase Auth Emulator. Without either, the app still
boots and shows the login page, but sign-in fails.

For a deployed build, set `VITE_API_BASE_URL` to the API origin + prefix
(e.g. `https://api.example/api/v1`).

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test` | Vitest (run once) |
| `npm run test:watch` | Vitest in watch mode |

Tests live next to the code they cover (`*.test.ts` / `*.test.tsx`); jsdom +
Testing Library, config in `vite.config.ts`, setup in `src/test/setup.ts`.

## Layout

```
src/
├── api/endpoints.ts     typed API client (one layer, matches Docs/API_CONTRACT.md)
├── context/AuthContext  useAuth(): user, login, logout, can(role), resetPassword
├── lib/                 firebase app/auth, axios instance (+ bearer token), query client, formatters
├── types/api.ts         response types mirrored from the contract
├── components/
│   ├── ui/              Button, Card, Badge, Table, Field, StatCard, States, …
│   ├── layout/          AppShell, Sidebar, Topbar (user menu)
│   ├── RequireAuth.tsx  route guard (+ optional role)
│   ├── Toast.tsx        toast provider + useToast()
│   └── ErrorBoundary.tsx
└── pages/               one file per route (LoginPage, UsersPage, …)
```

Auth: sign-in/out goes through the Firebase client SDK (`src/lib/firebase.ts`);
`AuthContext` fetches the local profile from `/auth/me` whenever Firebase
reports a signed-in user. The axios interceptor attaches the Firebase ID
token and redirects to `/login` on `401`. `can("reviewer")` etc. gate
role-specific actions. `RequireAuth` guards the routes.

Data fetching goes through TanStack Query; components never call axios directly.
Design tokens live as CSS variables in `src/index.css` and are surfaced to
Tailwind in `tailwind.config.js` (`brand`, `ink`, `line`, `ok/warn/danger`, …).
