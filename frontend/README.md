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
- Auth token is stored in localStorage key `temperance.session`.
- The public app is served from the root path at `https://app.temperance-rtl.work`.

## Main frontend surfaces

- Login and protected routing
- Dashboard and activity detail drill-down
- Week planner, planned activities, and weekly outlook
- Wellness, settings, and athlete progression
- Data extract controls for Garmin credentials, sync, and reset

## String-contract awareness

The frontend displays and submits normalized workout strings rather than inventing a separate client-only schema.

- Planned and custom activity entry text should stay compatible with backend parsing rules
- Generated activity text is intentionally reparseable by the backend, so UI copy changes should not silently mutate those strings
- If a feature starts editing `workout_text` or `activity_text`, validate the change against backend parsing tests before assuming it is display-only

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
