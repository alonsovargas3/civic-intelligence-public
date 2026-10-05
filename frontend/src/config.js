// Single source of truth for static-build mode. Set VITE_STATIC=1 at build time
// (e.g. `VITE_STATIC=1 npm run build`) to produce the database-free CDN variant.
// Unset (default) keeps live /v1 API behavior — nothing static ships by default.
export const STATIC = import.meta.env.VITE_STATIC === '1'
