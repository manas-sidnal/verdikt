# Verdikt frontend

The "Agent lab": a React + TypeScript + Vite single-page UI for Verdikt. Pick a sample repo and an agent
behavior, run a verification, and see each claim judged against real test runs.

## Run it

The backend must be running first (see the [root README](../README.md)).

```bash
npm install
npm run dev        # http://localhost:5173
```

The UI talks to the API at `http://127.0.0.1:8000` by default. To point it elsewhere, create `frontend/.env`:

```env
VITE_API_BASE_URL=https://your-api.example.com
```

Vite reads this at **build time**, so rebuild after changing it. The backend must also list the frontend's
origin in `VERDIKT_CORS_ORIGINS`.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the dev server |
| `npm run build` | Type-check and build to `dist/` (`tsc -b && vite build`) |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |

## What the UI does

- **Starts empty.** Choose a repository, then an agent behavior; the agent's report fills in.
- **Replay or Live.** Replay uses scripted claims and works offline. Live lets you edit the report and has
  Nemotron on Nebius Token Factory extract the claims.
- **Verdict first.** The result opens with the overall verdict (`VERIFIED`, `CONTRADICTED` or
  `INSUFFICIENT EVIDENCE`) and a one-line summary.
- **Evidence for every claim.** Each claim card shows its check, verdict, evidence source and the raw pytest output.
- **Test integrity.** Flags patches that tried to edit protected test files.
- **Before and after.** The test run on the unpatched repo next to the run on the agent's patch.

## Structure

```
src/
  App.tsx     the whole UI (components, API calls, types)
  App.css     styles (plain CSS with custom properties)
  main.tsx    React entry point
  index.css   global styles (currently empty)
public/       favicon
```

API calls: `GET /demo/config` on load and `POST /demo/verify` on each run.
