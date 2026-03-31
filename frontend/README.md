# Temperance Frontend

React + Vite + TypeScript frontend for Temperance.

## Quick start

```bash
cd /Users/matheus/Temperance/frontend
npm install
npm run dev
```

Dev server: `http://127.0.0.1:5173`

## Build

```bash
npm run build
npm run preview
```

## Backend integration notes

- API base path is configured in `src/api/config.ts` as `/api`.
- During local dev, Vite proxy in `vite.config.ts` forwards `/api/*` and `/health` to `http://127.0.0.1:8000`.
- The backend still accepts `/api/v1/*` as a compatibility alias during the transition.
- Auth token is stored in localStorage key `temperance.session` and falls back to the older key during migration.

### Update points for backend contracts

1. `src/api/config.ts`
- Adjust endpoint paths if backend changes.

2. `src/features/auth/services/auth-api.ts`
- Align login and `me` response types if fields differ.

3. `src/features/weekly-outlook/types/weekly-outlook.ts`
- Update raw contract types if payload shape changes.

4. `src/features/weekly-outlook/utils/weekly-outlook-mapper.ts`
- Keep backend-specific assumptions isolated in the mapper.

5. `src/features/weekly-outlook/services/weekly-outlook-api.ts`
- Add extra query params if backend requires additional filters.
