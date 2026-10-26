# Verdikt Frontend

The React + TypeScript dashboard for the Verdikt AI agent verification system.

Built with [Vite](https://vite.dev/), [React 19](https://react.dev/), [Tailwind CSS v4](https://tailwindcss.com/), and [Lucide icons](https://lucide.dev/).

---

## Getting Started

From this directory:

```bash
npm install
npm run dev
```

The dev server runs at `http://localhost:5173`.

---

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the Vite dev server with HMR |
| `npm run build` | Type-check and build for production |
| `npm run preview` | Preview the production build locally |
| `npm run lint` | Run ESLint |

---

## Structure

```
frontend/
├── src/
│   ├── App.tsx       # Main Verdikt dashboard component
│   ├── App.css       # Component styles
│   ├── main.tsx      # React entry point
│   └── index.css     # Global styles
├── public/           # Static assets
├── index.html        # HTML shell
└── vite.config.ts    # Vite configuration
```

---

## Notes

- The frontend is currently a **UI prototype**. The verification pipeline runs via the Python backend; the two are not yet connected end-to-end.
- See the [root README](../README.md) for full project setup instructions.
