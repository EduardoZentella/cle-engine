# CLE Engine Frontend

Frontend application for the CLE Engine platform.

This client is built with React + TypeScript + Vite and consumes the backend recommendation APIs to support:

- contextual translation analysis,
- vocabulary recommendation rendering,
- adaptive practice generation.

## Tech Stack

- React 19
- TypeScript 5
- Vite 8
- ESLint 9

## What This Frontend Does

The interface is split into three application areas:

1. Landing

- Displays learner profile status.
- Shows backend connectivity state.
- Provides navigation to translation and practice flows.

2. Translation

- Sends contextual translation requests to backend.
- Receives and displays reranked recommendations.
- Shows predicted level and recommended model action.

3. Practice

- Requests generated exercises from backend.
- Allows answer selection and score evaluation.
- Supports regeneration of exercise sets.

## Source Layout

```text
src/
  App.tsx                       # App shell, navigation wiring, user/profile sync
  App.css                       # Main design system and page styling
  index.css                     # Global typography and root defaults
  main.tsx                      # React entry point
  landing/
    LandingPage.tsx             # Overview page
  menu/
    NavigationDrawer.tsx        # Drawer navigation
  translation/
    TranslationPage.tsx         # Translation + context form
  recommendations/
    RecommendationSection.tsx   # Recommendation list UI
  practice/
    PracticePage.tsx            # Exercise flow and scoring
  services/
    api.ts                      # Typed HTTP client for backend API
  types/
    app.ts                      # Shared app-level types
```

## API Integration

API base URL is read from `VITE_API_URL`.

Used endpoints:

- `POST /api/v1/users/upsert`
- `POST /api/v1/recommendations/contextual`
- `GET /api/v1/practice/generate`

The frontend API client is implemented in `src/services/api.ts` and mirrors backend schemas in `app/api/schemas.py`.

## Environment Variables

### Local non-Docker development

Create `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

### Docker Compose development

`VITE_API_URL` is fetched from Vault at container startup (not hardcoded in frontend service env).

Vault path used by the frontend container:

- `secret/cle-engine/frontend` (kv-v2)
  - key: `VITE_API_URL`

## Run Commands

From `frontend/`:

```bash
pnpm install
pnpm dev
```

Build:

```bash
pnpm build
```

Lint:

```bash
pnpm lint
```

Preview production build:

```bash
pnpm preview
```

## Docker Workflow

From repository root:

```bash
docker compose up --build
```

Frontend will be available at:

- http://localhost:5173

## Behavior Notes

- A stable `user_id` is generated with `crypto.randomUUID()` and persisted in local storage.
- Learner profile is persisted in local storage and synchronized to backend.
- Recommendation source labels are derived from backend score fields (`fusion`, `vector`, `lexical`).
- Practice scoring handles optional backend fields safely.

## Troubleshooting

### Frontend starts but cannot call backend

- Confirm backend health: `http://localhost:8000/health`
- Confirm Vault has `VITE_API_URL` under `secret/cle-engine/frontend`
- Check frontend logs in compose output

### Type mismatch after backend schema changes

- Update `src/services/api.ts` to match backend contracts
- Re-run:

```bash
pnpm lint
pnpm build
```

### CORS issues

- Ensure backend CORS configuration allows the frontend origin (`http://localhost:5173`)
