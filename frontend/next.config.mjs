/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static HTML/JS/CSS export. The Handler API (FastAPI) serves the built `out/`
  // same-origin, exactly as it served the old Alpine shell — the browser calls the
  // authed API with relative paths, so there is no separate frontend server to run.
  output: "export",
  reactStrictMode: true,
  // Emit each route as `<route>/index.html` (not `<route>.html`) so the FastAPI static
  // mount — Starlette's StaticFiles(html=True) — serves clean, slash-terminated URLs like
  // `/repositories/` straight from disk, with no SPA rewrite or per-route server config.
  trailingSlash: true,
  // The export is served from disk with no image optimizer behind it.
  images: { unoptimized: true },
};

export default nextConfig;
