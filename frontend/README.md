# Verdikt Frontend

The React + TypeScript dashboard for the Verdikt AI agent verification system.

Built with [Vite](https://vite.dev/), [React 19](https://react.dev/), [Tailwind CSS v4](https://tailwindcss.com/), and [Lucide icons](https://lucide.dev/).

---

## Getting Started

### 1. Install dependencies

From this directory:

```bash
npm install
```

### 2. Configure environment (optional)

The frontend connects to the FastAPI verification backend at `http://127.0.0.1:8000` by default. To point to a custom URL, create a `.env` file in `frontend/`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 3. Run development server

```bash
npm run dev
```

The dev server runs at `http://localhost:5173`.

---

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the Vite dev server with HMR |
| `npm run build` | Type-check and build for production (`tsc -b && vite build`) |
| `npm run preview` | Preview the production build locally |
| `npm run lint` | Run ESLint |

---

## Structure

```
frontend/
├── src/
│   ├── App.tsx       # Main Verdikt dashboard component (connected to /verify API)
│   ├── App.css       # Verdikt dark design system styles
│   ├── main.tsx      # React entry point
│   ├── index.css     # Base Tailwind styles
│   └── assets/       # Icons and graphics
├── public/           # Static assets
├── index.html        # HTML shell
└── vite.config.ts    # Vite configuration
```

---

## Features

- **Live claim verification**: Submits natural language claims to the backend verification engine.
- **Stage breakdown**: Displays verification planning, evidence collection, and verdict evaluation stages.
- **Verdict badges**: Clean visual status for `VERIFIED` (green), `CONTRADICTED` (red), and `INSUFFICIENT EVIDENCE` (amber).
- **Execution telemetry**: Shows test status, stdout/stderr inspection, and check runner logs.

See the [root README](../README.md) for complete end-to-end system setup and backend API documentation.
